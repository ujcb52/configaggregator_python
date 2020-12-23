# configaggregator_python

1. OU에서 계정 정보를 가져옵니다.

2. Security Core Account에 Config Aggregator 설정을 assume_role을 통해 배포합니다.

[개선 필요 사항]

- event 스트림 받아서 cloudformation error 반환시키는 내용 테스트

- cloudformation 내에 python code 가 있는 부분 s3에 업로드하고 참조하는 코드로 변경