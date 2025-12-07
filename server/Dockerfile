FROM nvidia/cuda:13.0.2-cudnn-devel-ubuntu24.04 AS base
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 \
        python-is-python3

FROM base AS python-base

ENV PROJECT_PATH=/cloud_server
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libssl-dev

WORKDIR /cloud_server

RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=${PROJECT_PATH}/pyproject.toml,ro \
    --mount=type=bind,source=uv.lock,target=${PROJECT_PATH}/uv.lock,ro \
    --mount=type=bind,source=.python-version,target=${PROJECT_PATH}/.python-version,ro \
    uv sync --frozen --no-install-project --no-install-workspace --no-dev

COPY --exclude=*.py --exclude=*.md src/ ${PROJECT_PATH}/src

RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=${PROJECT_PATH}/pyproject.toml,ro \
    --mount=type=bind,source=uv.lock,target=${PROJECT_PATH}/uv.lock,ro \
    --mount=type=bind,source=.python-version,target=${PROJECT_PATH}/.python-version,ro \
    uv sync --locked --no-dev

FROM base AS dev
ARG DEBIAN_FRONTEND=noninteractive

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=python-base /root/.cache/uv/ /root/.cache/uv/
COPY --from=python-base /cloud_server /cloud_server

WORKDIR /cloud_server

CMD ["/bin/bash"]

FROM base AS prod
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git
        
WORKDIR /cloud_server

COPY --from=python-base /cloud_server /cloud_server

COPY . .

CMD [".venv/bin/python", "-m", "src"]
