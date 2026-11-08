# test-protocol in a container, with WeasyPrint and its system libraries, so PDF
# output needs no local installation. Runs in /data; mount your results there and
# run as your own user so the files you get back belong to you.
#
#   docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/data" ghcr.io/steitec/test-protocol \
#       result.json --limits limits.toml -o protocol.html --pdf protocol.pdf
FROM python:3.13-slim
LABEL org.opencontainers.image.source=https://github.com/steitec/test-protocol \
      org.opencontainers.image.description="Turn raw test results into a printable test protocol (HTML, PDF, JSON)" \
      org.opencontainers.image.licenses=MIT

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# The protocol asks for system-ui, which fontconfig would otherwise resolve to the
# first font it finds (a monospaced one here).
COPY <<'FONTS' /etc/fonts/local.conf
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias binding="same"><family>system-ui</family><prefer><family>Liberation Sans</family></prefer></alias>
  <alias binding="same"><family>sans-serif</family><prefer><family>Liberation Sans</family></prefer></alias>
</fontconfig>
FONTS

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[pdf]" && rm -rf /src

RUN useradd --create-home --uid 10001 protocol && install -d -o protocol /data
# With --user there is no home directory; fontconfig still needs a place for its cache.
ENV XDG_CACHE_HOME=/tmp/.cache
USER protocol
WORKDIR /data

ENTRYPOINT ["test-protocol"]
CMD ["--help"]
