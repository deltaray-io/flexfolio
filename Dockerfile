FROM python:3.5 AS build
RUN python3 -m venv /venv

ADD requirements.txt /
RUN /venv/bin/pip install --no-cache-dir -r /requirements.txt

ADD . /flexfolio
RUN /venv/bin/pip install --no-cache-dir /flexfolio

WORKDIR /flexfolio

# Run tests
ADD requirements.txt test-requirements.txt /
RUN python3 -m venv /venv-test && \
          /venv-test/bin/pip install -r /requirements.txt -r /test-requirements.txt && \
          /venv-test/bin/tox  &&  \
          rm -rf /venv-test

FROM python:3.5-slim AS production

COPY --from=build /venv /venv

ENTRYPOINT ["/venv/bin/flexfolio"]
