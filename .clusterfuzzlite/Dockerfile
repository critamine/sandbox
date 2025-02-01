FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:f082bfb3df3badf52a652bf4a9694beb2e979ee5476da22e97b2ddaaffb16795
COPY . $SRC/hivebox
WORKDIR $SRC/hivebox
RUN pip3 install --require-hashes -r requirements.txt
RUN pip3 install .
COPY .clusterfuzzlite/build.sh $SRC/
