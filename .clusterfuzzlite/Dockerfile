FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:21d065e1b72764f938247c38a47698ffc7ac4c9dcbd3eb150532a4e7c9ac2af7
COPY . $SRC/hivebox
WORKDIR $SRC/hivebox
RUN pip3 install --require-hashes -r requirements.txt
RUN pip3 install .
COPY .clusterfuzzlite/build.sh $SRC/
