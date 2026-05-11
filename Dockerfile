FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src/ ./src/
ENV COPILOT_MCP_PORT=8080
EXPOSE 8080
ENTRYPOINT ["uv", "run", "llm-sca", "mcp", "serve"]
