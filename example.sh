# 1. Add blog index URLs to monitor
uv run newshive source add  https://agents.blog/
uv run newshive source add  https://ai.meta.com/blog/
uv run newshive source add  https://bair.berkeley.edu/blog/archive/
uv run newshive source add  https://blog.agent.ai/
uv run newshive source add  https://blog.google/technology/ai/
uv run newshive source add  https://cloud.google.com/blog/
uv run newshive source add  https://deepmind.google/blog/
uv run newshive source add  https://developers.googleblog.com/
uv run newshive source add  https://eugeneyan.com/writing/
uv run newshive source add  https://github.com/topics/ai-agents
uv run newshive source add  https://hamel.dev/
uv run newshive source add  https://huggingface.co/blog
uv run newshive source add  https://huyenchip.com/
uv run newshive source add  https://jxnl.co/writing/
uv run newshive source add  https://karpathy.ai/
uv run newshive source add  https://lilianweng.github.io/
uv run newshive source add  https://medium.com/me/following-feed/publications/e52cf94d98af
uv run newshive source add  https://news.ycombinator.com/
uv run newshive source add  https://openai.com/news/
uv run newshive source add  https://sebastianraschka.com/blog/
uv run newshive source add  https://trendshift.io/
uv run newshive source add  https://www.anthropic.com/news
uv run newshive source add  https://www.interconnects.ai/
uv run newshive source add  https://www.microsoft.com/en-us/research/blog/
uv run newshive source add  https://www.philschmid.de/
uv run newshive source add  https://www.producthunt.com/leaderboard/

# 2. Collect new articles (fetch index → delta → download)
uv run newshive collect

# 3. Extract & summarize downloaded articles
uv run newshive process
