import pytest
from unittest.mock import patch, MagicMock
from ai_news_summarizer.summarizer import Summarizer

@patch("ai_news_summarizer.summarizer.ollama.chat")
def test_summarize(mock_chat):
    # Setup the mock to return a known summary
    mock_response = MagicMock()
    mock_response.message.content = "# AI Summary\n\nThis is a mocked summary."
    mock_chat.return_value = mock_response

    summarizer = Summarizer(model_name="test-model")
    result = summarizer.summarize("Long article text goes here.")
    
    assert result == "# AI Summary\n\nThis is a mocked summary."
    
    # Verify the call to the mock
    mock_chat.assert_called_once()
    call_args = mock_chat.call_args[1]
    assert call_args["model"] == "test-model"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["role"] == "system"
    assert "Google Cloud" in call_args["messages"][0]["content"]
    assert "Gemini" in call_args["messages"][0]["content"]
    assert call_args["messages"][1]["role"] == "user"
    assert call_args["messages"][1]["content"] == "Long article text goes here."
