from openrepo_agent.intent import IntentRouter


def test_routes_setup_question() -> None:
    intent = IntentRouter().route("How do I install and run this project?")
    assert intent.name == "setup_help"


def test_routes_bug_question() -> None:
    intent = IntentRouter().route("I get a traceback when starting the CLI")
    assert intent.name == "bug_triage"


def test_routes_patch_question() -> None:
    intent = IntentRouter().route("Please propose a patch and add test coverage")
    assert intent.name == "patch_request"
