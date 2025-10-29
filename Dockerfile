FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "random_coffee.main"]