# 1. Add blog index URLs to monitor
uv run newshive source add https://huggingface.co/blog
uv run newshive source add https://lilianweng.github.io/
uv run newshive source add https://karpathy.ai/

# 2. Collect new articles (fetch index → delta → download)
uv run newshive collect

# 3. Extract & summarize downloaded articles
uv run newshive process
