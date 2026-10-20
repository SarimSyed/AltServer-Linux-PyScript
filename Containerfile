FROM docker.io/dadoum/anisette-server@sha256:786692cbfed1fc2c2123e2b1728858c254d355db20ba9769914efcb5edb2329e
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libplist-2.0-4 && rm -rf /var/lib/apt/lists/*
USER Chester
