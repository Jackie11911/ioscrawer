import requests
import re
import subprocess
import os
import tempfile
import zipfile
import plistlib

def download_ipa_file(url):
    # 提取国籍信息和 ID
    url_info = extract_url_info(url)
    country = url_info['country']
    app_id = url_info['id']

    # 登录逻辑
    if country == 'cn':
        login_command = [
            'ipatool', 'auth', 'login',
            '-e', 'IOSguoqu@nfmistake.xyz',
            '-p', 'dH8L3q9Pm',
            '--keychain-passphrase', '123456'
        ]
    elif country == 'us':
        login_command = [
            'ipatool', 'auth', 'login',
            '-e', 'fany37827@gmail.com',
            '-p', 'dH8L3q9Pm',
            '--keychain-passphrase', '123456'
        ]
    else:
        raise ValueError("Unsupported country code")

    # 执行登录命令
    subprocess.run(' '.join(login_command), shell=True, check=True)

    # 下载逻辑
    download_command = [
        'ipatool', 'download',
        '-i', app_id,
        '--purchase',
        '-o',f'ipa/{app_id}.ipa',
        '--keychain-passphrase', '123456'
    ]

    # 执行下载命令
    subprocess.run(' '.join(download_command), shell=True, check=True)

    # 解压 ipa 文件并提取 bundle ID
    ipa_path = f'ipa/{app_id}.ipa'
    bundle_id, app_name = extract_basic_ifo(ipa_path)

    return app_id, country, bundle_id, app_name

def extract_url_info(url):
    """
    提取 URL 中的国籍信息和 ID。
    :param url: 目标 URL
    :return: 包含国籍信息和 ID 的字典
    """
    match = re.search(r'apps\.apple\.com/(?P<country>\w+)/app/.*/id(?P<id>\d+)', url)
    if match:
        return {
            'country': match.group('country'),
            'id': match.group('id')
        }
    else:
        raise ValueError("Invalid URL format")

def extract_basic_ifo(ipa_path):
    """
    从 ipa 文件中提取 bundle ID。
    :param ipa_path: ipa 文件路径
    :return: bundle ID
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(ipa_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # 定位 Info.plist 文件
        plist_path = os.path.join(temp_dir, 'Payload', os.listdir(os.path.join(temp_dir, 'Payload'))[0], 'Info.plist')
        with open(plist_path, 'rb') as plist_file:
            plist_data = plistlib.load(plist_file)
            return plist_data.get('CFBundleIdentifier', 'Unknown'), plist_data.get('CFBundleDisplayName', 'Unknown')
