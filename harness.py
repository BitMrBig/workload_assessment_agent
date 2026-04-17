import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from core.config import load_config
from core.llm import LLMClient
from core.merge import merge_results
from core.module import flatten_modules
from core.prompts import load_prompt
from core.session import SessionStore
from core.validation import (
    ensure_assignments_cover_modules,
    ensure_estimations_cover_modules,
    ensure_no_duplicate_agents,
    ensure_valid_agent_names,
    ensure_valid_presale_response,
    normalize_estimations,
)
from output.excel import save_excel
from output.report import build_report


ROLE_AGENTS = ["product", "ui", "backend", "frontend", "app", "testing", "algorithm", "ops"]


class HarnessRunner:
    def __init__(self, config, config_path: Path):
        self.config = config
        self.client = LLMClient(config)
        self.session_store = SessionStore(
            base_dir=Path(config["app"]["output_dir"]),
            config_path=config_path,
        )

    @staticmethod
    def _log(message: str) -> None:
        print(f"[progress] {message}")

    @staticmethod
    def _log_agent_call(agent_name: str, phase: str) -> None:
        print(f"[agent:{agent_name}] {phase}")

    def _call_agent(self, agent_name: str, payload: dict) -> dict:
        self._log_agent_call(agent_name, "request started")
        prompt = load_prompt(agent_name)
        response = self.client.generate_json(
            system_prompt=prompt,
            payload=payload,
        )
        self._log_agent_call(agent_name, "response received")
        return response

    def _run_presale(
        self, requirement_text: str, max_rounds: int, non_interactive: bool
    ) -> Tuple[dict, list]:
        clarification_history = []
        presale_payload = {
            "project_requirements": requirement_text,
            "clarification_history": clarification_history,
            "available_roles": ROLE_AGENTS,
            "max_module_depth": 1,
        }

        for round_index in range(max_rounds + 1):
            if round_index == 0:
                self._log("Step 1/6: running presale_agent on the original requirement.")
            else:
                self._log(f"Step 1/6: running presale_agent after clarification round {round_index}.")
            presale_result = self._call_agent("presale_agent", presale_payload)
            ensure_valid_presale_response(presale_result)

            if presale_result["next_action"] == "done":
                self._log("Presale completed. Requirement is clear enough to continue.")
                return presale_result, clarification_history

            if round_index == max_rounds:
                raise RuntimeError("Presale agent still requires clarification after reaching max_clarify_rounds.")

            questions = presale_result.get("clarifications", [])
            if not questions:
                raise RuntimeError("Presale agent requested clarification without providing questions.")

            if non_interactive:
                raise RuntimeError(
                    "Clarification is required but CLI is running in non-interactive mode. "
                    "Please rerun without --non-interactive or refine the input."
                )

            self._log(
                f"Presale requested clarification. Entering round {round_index + 1}/{max_rounds}."
            )
            print("\n需要澄清以下问题：")
            answers = []
            for index, question in enumerate(questions, start=1):
                answer = input(f"[Q{index}] {question}\n> ").strip()
                answers.append({"question": question, "answer": answer})

            clarification_history.append(
                {
                    "round": round_index + 1,
                    "questions": questions,
                    "answers": answers,
                }
            )
            presale_payload["clarification_history"] = clarification_history

        raise RuntimeError("Unexpected clarification loop exit.")

    def run(
        self, requirement_text: str, non_interactive: bool = False, session_name: Optional[str] = None
    ) -> Path:
        max_rounds = int(self.config["app"]["max_clarify_rounds"])
        effort_buffer_ratio = float(self.config["app"]["effort_buffer_ratio"])
        self._log("Step 0/6: creating session directory.")
        session_dir = self.session_store.create_session_dir(session_name=session_name)

        presale_result, clarification_history = self._run_presale(
            requirement_text=requirement_text,
            max_rounds=max_rounds,
            non_interactive=non_interactive,
        )

        modules = flatten_modules(presale_result["modules"])
        assignments = presale_result["module_assignments"]
        self._log(f"Step 2/6: validating modules and assignments for {len(modules)} leaf modules.")
        ensure_assignments_cover_modules(modules, assignments)

        self._log("Step 3/6: running dispatcher_agent for recommendation only.")
        dispatch_payload = {
            "modules": modules,
            "module_assignments": assignments,
            "available_roles": ROLE_AGENTS,
        }
        dispatch_result = self._call_agent("dispatcher_agent", dispatch_payload)
        recommended_agents = dispatch_result.get("active_agents", [])
        ensure_no_duplicate_agents(recommended_agents)
        ensure_valid_agent_names(recommended_agents, ROLE_AGENTS)
        active_agents = list(ROLE_AGENTS)
        self._log(
            "Dispatcher recommendation: "
            + (", ".join(recommended_agents) if recommended_agents else "none")
            + ". Execution policy: all roles will evaluate and decide whether to contribute."
        )

        self._log(f"Step 4/6: running role agents ({', '.join(active_agents)}).")
        role_results = {}
        for agent_name in active_agents:
            self._log(f"Running {agent_name}_agent.")
            assigned_modules = [m for m in modules if agent_name in assignments.get(m, [])]
            role_payload = {
                "project_requirements": requirement_text,
                "modules": modules,
                "assignments": assignments,
                "assigned_modules": assigned_modules,
            }
            role_result = self._call_agent(f"{agent_name}_agent", role_payload)
            role_result["estimations"] = normalize_estimations(
                modules=modules,
                estimations=role_result.get("estimations", []),
                role_name=agent_name,
                assigned_modules=assigned_modules,
            )
            ensure_estimations_cover_modules(modules, role_result.get("estimations", []), agent_name)
            role_results[agent_name] = role_result

        self._log("Step 5/6: merging role estimations and building report.")
        table_rows = merge_results(
            modules=modules,
            assignments=assignments,
            results=role_results,
            roles=ROLE_AGENTS,
            effort_buffer_ratio=effort_buffer_ratio,
        )
        report_text = build_report(
            requirement_text=requirement_text,
            module_tree=presale_result["modules"],
            modules=modules,
            assignments=assignments,
            rows=table_rows,
            active_agents=active_agents,
            clarification_history=clarification_history,
            effort_buffer_ratio=effort_buffer_ratio,
        )

        self._log("Step 6/6: exporting report, session, and Excel.")
        save_excel(presale_result["modules"], table_rows, session_dir / "workload.xlsx")
        self.session_store.write_text(session_dir / "report.md", report_text)
        self.session_store.write_json(
            session_dir / "session.json",
            {
                "input": requirement_text,
                "clarification_history": clarification_history,
                "presale_result": presale_result,
                "dispatch_result": dispatch_result,
                "recommended_agents": recommended_agents,
                "evaluation_agents": active_agents,
                "role_results": role_results,
                "effort_buffer_ratio": effort_buffer_ratio,
                "table_rows": table_rows,
                "report_path": str(session_dir / "report.md"),
                "excel_path": str(session_dir / "workload.xlsx"),
            },
        )

        return session_dir


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structured workload assessment CLI harness.")
    parser.add_argument("--config", default="config.toml", help="Path to config TOML file.")
    parser.add_argument("--input", help="Requirement text.")
    parser.add_argument("--input-file", help="Path to a text file containing requirements.")
    parser.add_argument("--session-name", help="Optional human-friendly session directory prefix.")
    parser.add_argument("--non-interactive", action="store_true", help="Fail instead of asking clarification questions.")
    return parser.parse_args(argv)


def _read_input_text(args: argparse.Namespace) -> str:
    if bool(args.input) == bool(args.input_file):
        raise SystemExit("Use exactly one of --input or --input-file.")

    if args.input:
        return args.input.strip()

    return Path(args.input_file).read_text(encoding="utf-8").strip()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config)
    config = load_config(config_path)
    requirement_text = _read_input_text(args)

    runner = HarnessRunner(config=config, config_path=config_path)
    try:
        session_dir = runner.run(
            requirement_text=requirement_text,
            non_interactive=args.non_interactive,
            session_name=args.session_name,
        )
    except Exception as exc:
        print(f"评估失败: {exc}", file=sys.stderr)
        return 1

    print(f"评估完成。输出目录: {session_dir}")
    print(f"- Excel: {session_dir / 'workload.xlsx'}")
    print(f"- Report: {session_dir / 'report.md'}")
    print(f"- Session: {session_dir / 'session.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
