FROM ubuntu:18.04
RUN apt-get update && apt-get install -y python3 python3-requests git
RUN git clone https://github.com/manimarius/tiny-matrix-bot.git
RUN git clone https://github.com/matrix-org/matrix-python-sdk
WORKDIR /tiny-matrix-bot
RUN mkdir data && ln -s ../matrix-python-sdk/matrix_client
ENTRYPOINT ["./tiny-matrix-bot.py"]
CMD ["-E"]
