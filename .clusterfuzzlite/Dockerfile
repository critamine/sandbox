FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:fb67bbf60d368d6892e911ddaefd6812f4003d86013d356abd51c34b3f44b54e
COPY . $SRC/hivebox
WORKDIR $SRC/hivebox
RUN pip3 install --require-hashes -r requirements.txt
RUN pip3 install .
COPY .clusterfuzzlite/build.sh $SRC/
