from app.services import telegram as tg


def test_should_queue_proactive_message_on_init_conversation_error() -> None:
    assert tg._should_queue_proactive_message("bot can't initiate conversation")
    assert tg._should_queue_proactive_message("chat not found")
    assert not tg._should_queue_proactive_message("blocked by the user")


def test_build_start_link_uses_bot_username() -> None:
    assert tg._build_start_link("@wingbank", "abc123") == "https://t.me/wingbank?start=abc123"
