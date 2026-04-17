import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from core.config import load_config
from core.llm import LLMClient
from core.merge import merge_results
from core.module import build_leaf_module_detail_map, build_leaf_module_details, flatten_modules
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

    @staticmethod
    def _print_module_list(modules: list[str]) -> None:
        print("\n当前确认后的需求模块列表：")
        for index, module_name in enumerate(modules, start=1):
            print(f"{index}. {module_name}")

    @staticmethod
    def _print_module_details(module_details: list[dict]) -> None:
        print("\n当前确认后的需求模块与功能描述：")
        for index, item in enumerate(module_details, start=1):
            description = item.get("description", "").strip() or "无描述"
            print(f"{index}. {item['name']}")
            print(f"   描述: {description}")

    def _collect_presale_clarifications(
        self,
        presale_payload: dict,
        initial_result: dict,
        clarification_history: list,
        max_rounds: int,
        non_interactive: bool,
        consumed_rounds: int,
        stage_label: str,
    ) -> Tuple[dict, int]:
        presale_result = initial_result
        while presale_result["next_action"] == "clarify":
            if consumed_rounds >= max_rounds:
                raise RuntimeError("Presale agent still requires clarification after reaching max_clarify_rounds.")

            questions = presale_result.get("clarifications", [])
            if not questions:
                raise RuntimeError("Presale agent requested clarification without providing questions.")

            if non_interactive:
                raise RuntimeError(
                    "Clarification is required but CLI is running in non-interactive mode. "
                    "Please rerun without --non-interactive or refine the input."
                )

            consumed_rounds += 1
            self._log(
                f"Presale requested clarification during {stage_label}. Entering round {consumed_rounds}/{max_rounds}."
            )
            print("\n需要澄清以下问题：")
            answers = []
            for index, question in enumerate(questions, start=1):
                answer = input(f"[Q{index}] {question}\n> ").strip()
                answers.append({"question": question, "answer": answer})

            clarification_history.append(
                {
                    "stage": stage_label,
                    "round": consumed_rounds,
                    "questions": questions,
                    "answers": answers,
                }
            )
            presale_payload["clarification_history"] = clarification_history
            presale_result = self._call_agent("presale_agent", presale_payload)
            ensure_valid_presale_response(presale_result)

        return presale_result, consumed_rounds

    def _run_presale(
        self, requirement_text: str, max_rounds: int, non_interactive: bool
    ) -> Tuple[dict, list, list]:
        clarification_history = []
        module_confirmation_history = []
        presale_payload = {
            "project_requirements": requirement_text,
            "clarification_history": clarification_history,
            "available_roles": ROLE_AGENTS,
            "max_module_depth": 1,
            "current_modules": [],
            "current_module_assignments": {},
            "module_confirmation_feedback": "",
        }
        consumed_rounds = 0

        self._log("Step 1/7: running presale_agent on the original requirement.")
        presale_result = self._call_agent("presale_agent", presale_payload)
        ensure_valid_presale_response(presale_result)
        presale_result, consumed_rounds = self._collect_presale_clarifications(
            presale_payload=presale_payload,
            initial_result=presale_result,
            clarification_history=clarification_history,
            max_rounds=max_rounds,
            non_interactive=non_interactive,
            consumed_rounds=consumed_rounds,
            stage_label="initial_presale",
        )
        self._log("Presale completed. Requirement is clear enough to prepare confirmation.")

        confirmation_round = 0
        while True:
            modules = flatten_modules(presale_result["modules"])
            module_details = build_leaf_module_details(presale_result["modules"])
            self._log("Step 2/7: waiting for user confirmation on the module list.")
            self._print_module_details(module_details)

            if non_interactive:
                raise RuntimeError(
                    "Module confirmation is required but CLI is running in non-interactive mode. "
                    "Please rerun without --non-interactive."
                )

            user_input = input(
                "\n请确认以上需求模块。"
                "如确认请输入“确认”；如需调整，请直接描述要新增、删除或修改的需求。\n> "
            ).strip()

            confirmation_round += 1
            presale_payload = {
                "project_requirements": requirement_text,
                "clarification_history": clarification_history,
                "available_roles": ROLE_AGENTS,
                "max_module_depth": 1,
                "current_modules": presale_result["modules"],
                "current_module_assignments": presale_result["module_assignments"],
                "module_confirmation_feedback": user_input,
            }
            presale_result = self._call_agent("presale_agent", presale_payload)
            ensure_valid_presale_response(presale_result)
            presale_result, consumed_rounds = self._collect_presale_clarifications(
                presale_payload=presale_payload,
                initial_result=presale_result,
                clarification_history=clarification_history,
                max_rounds=max_rounds,
                non_interactive=non_interactive,
                consumed_rounds=consumed_rounds,
                stage_label="module_confirmation",
            )

            if presale_result["confirmation_status"] == "confirmed":
                module_confirmation_history.append(
                    {
                        "round": confirmation_round,
                        "modules": modules,
                        "module_details": module_details,
                        "user_input": user_input,
                        "agent_next_action": presale_result["next_action"],
                        "confirmed": True,
                    }
                )
                self._log("Module list confirmed by user. Proceeding to evaluation.")
                return presale_result, clarification_history, module_confirmation_history

            module_confirmation_history.append(
                    {
                        "round": confirmation_round,
                        "modules": modules,
                        "module_details": module_details,
                        "user_input": user_input,
                        "agent_next_action": presale_result["next_action"],
                        "confirmed": False,
                }
            )
            self._log("User requested module changes. Updated module list will be shown again for confirmation.")

    def run(
        self, requirement_text: str, non_interactive: bool = False, session_name: Optional[str] = None
    ) -> Path:
        max_rounds = int(self.config["app"]["max_clarify_rounds"])
        effort_buffer_ratio = float(self.config["app"]["effort_buffer_ratio"])
        self._log("Step 0/7: creating session directory.")
        session_dir = self.session_store.create_session_dir(session_name=session_name)

        presale_result, clarification_history, module_confirmation_history = self._run_presale(
            requirement_text=requirement_text,
            max_rounds=max_rounds,
            non_interactive=non_interactive,
        )

        modules = flatten_modules(presale_result["modules"])
        module_details = build_leaf_module_details(presale_result["modules"])
        module_detail_map = build_leaf_module_detail_map(presale_result["modules"])
        assignments = presale_result["module_assignments"]
        self._log(f"Step 3/7: validating modules and assignments for {len(modules)} leaf modules.")
        ensure_assignments_cover_modules(modules, assignments)

        self._log("Step 4/7: running dispatcher_agent for recommendation only.")
        dispatch_payload = {
            "modules": modules,
            "module_details": module_details,
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

        self._log(f"Step 5/7: running role agents ({', '.join(active_agents)}).")
        role_results = {}
        for agent_name in active_agents:
            self._log(f"Running {agent_name}_agent.")
            assigned_modules = [m for m in modules if agent_name in assignments.get(m, [])]
            assigned_module_details = [item for item in module_details if item["name"] in assigned_modules]
            role_payload = {
                "project_requirements": requirement_text,
                "modules": modules,
                "module_details": module_details,
                "assignments": assignments,
                "assigned_modules": assigned_modules,
                "assigned_module_details": assigned_module_details,
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

        self._log("Step 6/7: merging role estimations and building report.")
        table_rows = merge_results(
            modules=modules,
            module_detail_map=module_detail_map,
            assignments=assignments,
            results=role_results,
            roles=ROLE_AGENTS,
            effort_buffer_ratio=effort_buffer_ratio,
        )
        report_text = build_report(
            requirement_text=requirement_text,
            module_tree=presale_result["modules"],
            modules=modules,
            module_details=module_details,
            assignments=assignments,
            rows=table_rows,
            active_agents=active_agents,
            clarification_history=clarification_history,
            effort_buffer_ratio=effort_buffer_ratio,
        )

        self._log("Step 7/7: exporting report, session, and Excel.")
        save_excel(presale_result["modules"], table_rows, session_dir / "workload.xlsx")
        self.session_store.write_text(session_dir / "report.md", report_text)
        self.session_store.write_json(
            session_dir / "session.json",
            {
                "input": requirement_text,
                "clarification_history": clarification_history,
                "module_confirmation_history": module_confirmation_history,
                "presale_result": presale_result,
                "module_details": module_details,
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
