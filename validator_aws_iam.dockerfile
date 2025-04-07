FROM tensora/patrol-validator

COPY rds_iam_boot.py .
RUN pip install boto3
ENV AWS_REGION="eu-west-1"

CMD ["python", "-m", "rds_iam_boot"]
