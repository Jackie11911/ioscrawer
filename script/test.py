import requests

# 你的 Django 服务地址
BASE_URL = 'http://127.0.0.1:8001'

# 要测试的 IPA 下载链接
ipa_url = 'https://apps.apple.com/us/app/%E6%88%91%E7%9A%84%E6%95%99%E6%9C%83/id1091176017'

# 发送 process_ipa 请求
def test_process_ipa():
    params = {'url': ipa_url}
    response = requests.get(f'{BASE_URL}/process-ipa/', params=params)
    print('Status Code:', response.status_code)
    print('Response:', response.json())

if __name__ == '__main__':
    test_process_ipa()
