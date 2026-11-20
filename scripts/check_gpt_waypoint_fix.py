"""Offline regression check for the GPT newline-stop/waypoint parse fix."""

import argparse
import importlib.util
import runpy
import sys
import types
from pathlib import Path


def package(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-source", type=Path, required=True)
    args = parser.parse_args()
    base = args.baseline_source
    for name in ("llmastar", "llmastar.env", "llmastar.env.search",
                 "llmastar.pather", "llmastar.pather.llm_a_star"):
        package(name)
    search = sys.modules["llmastar.env.search"]
    search.env = types.ModuleType("llmastar.env.search.env")
    search.plotting = types.ModuleType("llmastar.env.search.plotting")
    model = types.ModuleType("llmastar.model")
    model.ChatGPT = model.Llama3 = object
    sys.modules[model.__name__] = model
    utils = types.ModuleType("llmastar.utils")
    utils.is_lines_collision = lambda *_: False
    utils.list_parse = runpy.run_path(str(base / "llmastar/utils/utils.py"))["list_parse"]
    sys.modules[utils.__name__] = utils
    load("llmastar.pather.llm_a_star.prompt",
         base / "llmastar/pather/llm_a_star/prompt.py")
    cls = load("llmastar.pather.llm_a_star.llm_a_star",
               base / "llmastar/pather/llm_a_star/llm_a_star.py").LLMAStar

    class FakeModel:
        response = "Generated Path: [[5, 5], [10, 10], [20, 20]]"
        call = None

        def ask(self, **kwargs):
            self.call = kwargs
            return self.response

    instance = cls.__new__(cls)
    instance.llm = "gpt"
    instance.prompt = "standard"
    instance.model = FakeModel()
    instance.s_start = (5, 5)
    instance.s_goal = (20, 20)
    instance.horizontal_barriers = []
    instance.vertical_barriers = []
    instance.range_x = [0, 50]
    instance.range_y = [0, 30]
    instance.obs = set()
    instance._initialize_llm_paths()
    assert instance.model.call["stop"] is None
    assert instance.target_list == [(5, 5), (10, 10), (20, 20)]
    instance.model.response = "We can plan a route around the obstacles."
    try:
        instance._initialize_llm_paths()
    except ValueError as exc:
        assert "waypoint list" in str(exc)
    else:
        raise AssertionError("Response without waypoints was silently accepted")
    openai = types.ModuleType("openai")

    class ChatCompletion:
        call = None

        @classmethod
        def create(cls, **kwargs):
            cls.call = kwargs
            return {"choices": [{"message": {"content": FakeModel.response}}]}

    openai.ChatCompletion = ChatCompletion
    sys.modules["openai"] = openai
    chatgpt = load("llmastar.model.chatgpt",
                   base / "llmastar/model/chatgpt.py").ChatGPT(
                       method="LLM-A*", sysprompt="", example=None)
    assert chatgpt.ask("prompt", stop=None, max_tokens=1000) == FakeModel.response
    assert ChatCompletion.call["stop"] is None
    print("PASS: full waypoint list retained; missing list raises an error")


if __name__ == "__main__":
    main()
