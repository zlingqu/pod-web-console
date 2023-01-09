FROM --platform=linux/amd64 python:3.6.8

WORKDIR /app

ADD . .

RUN pip3 install -r requirements.txt -i https://pip.nie.netease.com/simple

CMD ["python3", "run.py"]

# docker build --platform=linux/amd64 -t ncr.nie.netease.com/ccbaseimage/pod-web-console:v1 .