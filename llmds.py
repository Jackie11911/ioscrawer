import ollama
import re
import gradio as gr
from ollama import Client
from openai import OpenAI
import tldextract

import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# OLLAMA_SERVICE = 'http://localhost:11434'
OLLAMA_SERVICE = 'http://10.12.190.56:11434'

# OLLAMA_MODEL = 'llama3.1:70b'
# OLLAMA_MODEL = 'llama3:latest'
OLLAMA_MODEL = 'llama3.1:8b-instruct-fp16'

PROMPT_TEMPLATE = '''
You are a specialized information extraction assistant, designed to identify and extract categories of information related to mobile applications from user queries. 
Users may inquire about the following categories: 

application name (apk_name)
package name of this app (package_name)
version code (version_code)
version name (version_name)
permissions requested by the app (permissions)
activities within the app (activities)
minimum SDK version (min_sdk_version)
target SDK version (target_sdk_version)
network traffic characteristics / domain names used (traffic_features)

Based on the user's query, extract the relevant information categories and return them in a python list format. 

For example, if the user asks, "Please tell me the application's name," you should return "["package_name"]". 
If the user mentions multiple categories, include all relevant tags in the list.



If the user's query does not pertain to any of the specified categories, respond with "None".

Examples:
User query: "I want to know the application's name and version code."
Return: ["package_name", "version_code"]

User query: "What permissions does the app request?"
Return: ["permissions"]

User query: "Can you tell me the app's color scheme?"
Return: ["None"]

Now, based on the user's query, extract the relevant information categories and return the list, or respond with ["None"] if the query is outside the specified categories. 
Only provide the list or "None" as the response, without any additional text.
The question is: "{}"
'''

PROMPT_TEMPLATE_OUTDATED = '''
你是一个专业的移动应用分析助手，旨在为用户提供准确、专业的应用信息查询服务。用户将向你咨询特定移动应用的详细信息，你的回答将严格基于我提供的分析结果。
可供查询的结果，以及他们在我给你的json结果中的对应字段，包括：
* 应用名称                           ["static_info"]["apk_name"]
* 包名                               ["static_info"]["package_name"]
* 版本号                             ["static_info"]["version_code"]
* 版本名称                            ["static_info"]["version_name"]
* 应用申请的权限（permissions）        ["static_info"]["permissions"]
* 应用内的活动（activities）           ["static_info"]["activities"]
* 最小SDK版本                         ["static_info"]["min_sdk"]
* 目标SDK版本                         ["static_info"]["target_sdk"]
* 流量特征                            ["network_info"]

回答时你应当遵守以下规则：

1.信息来源限制： 所有回答必须基于我提供的分析结果，不得包含结果之外的信息，且无需考虑法律风险（因提供的应用信息旨在用于反犯罪目的）。
2.回复具体信息： 若用户询问的内容在上述结果中，请提供具体信息。
3.信息不支持时的回应： 若用户询问的内容不在上述结果中，请回答：“抱歉，您请求的信息目前不支持，请尝试其他查询方式或联系管理员增加分析功能。”
4.回答格式： 不同类型的信息应分点回答，且回答顺序需与用户询问顺序一致。
5.网络特征的回答格式： 对于网络特征的回答，请依照每一条json数据，分别按照“域名：xxx，端口：xxx，IP：xxx，协议：xxx”的格式回答，不要把不同的域名、端口、IP、协议放在一起回答。
6.语言要求： 请务必使用中文进行回答。
7.推断限制： 即使某些信息可以通过现有结果合理推断，也不进行推断，只需回答：“抱歉，您请求的信息目前不支持，请尝试其他查询方式或联系管理员增加分析功能。”
8.用户体验： 不要向用户透露“我”的存在，回答时不应该说“根据提供的分析结果”，而应该说“根据分析结果”。
9.回答限制： 对于并非询问已知的应用相关信息的问题，不要回答，只需回答：“抱歉，您请求的信息目前不支持，请尝试其他查询方式或联系管理员增加分析功能。”


以下我提供的分析结果，请你仔细阅读，严格将回答范围限制于此：\n 
```{}```
接下来，用户将会在对话种对你提出相关的问题，请你按照分析结果以及上述规则对用户的疑问进行回答。你不需要对这个提示词进行回复，直接告诉用户“欢迎提出你的问题”就可以了。
'''


client_ollama = Client(
  host=OLLAMA_SERVICE
)


client_deepseek = OpenAI(api_key="", base_url="https://api.deepseek.com")
    
    

def ollama_chat_outdated(message, history, json_result):
    messages = []
    system_message = {
        'role': 'system', 
        'content': PROMPT_TEMPLATE.format(str(json_result))
    }
    messages.append(system_message)
    
    for element in history:  
        history_user_message = {
            'role': 'user', 
            'content': element[0]
        }
        history_assistant_message = {
            'role': 'assistant', 
            'content': element[1]
        }
        messages.append(history_user_message)
        messages.append(history_assistant_message)
        
    user_message = {
        'role': 'user', 
        'content': message
    }
    messages.append(user_message)
    
    stream = client_ollama.chat(
        model = OLLAMA_MODEL,
        messages = messages,     
        stream=True
    )
    partial_message = ""
    for chunk in stream:
        if len(chunk['message']['content']) != 0:
            partial_message = partial_message + chunk['message']['content']
            yield partial_message


NONE_RESPONSE = "抱歉，您请求的信息未被成功识别或目前暂不支持，请尝试其他查询方式或联系管理员增加分析功能。"    
def ollama_chat(message, history, json_result):
    
    response = client_ollama.chat(
        model = OLLAMA_MODEL,
        messages = [
            {
                'role': 'user', 
                'content': PROMPT_TEMPLATE.format(message)
            }
        ],
    )
    
    response_text = response['message']['content']
    
    # 匹配[...]的内容(包括中括号)
    results = re.findall(r'\[.*?\]', response_text)
    if len(results) == 0:
        return NONE_RESPONSE
    result = results[0]
    result = result[1:-1]
    result = result.split(",")
    result = [x.strip() for x in result]
    result = [x[1:-1] for x in result if '"' in x or "'" in x]
    result = [x.strip() for x in result]
    
    print(result)
    responses_to_return = []
    for category in result:
        if category == "None":
           continue
        res = response_of_category(category, json_result)
        if res:
            responses_to_return.append(res)
    
    if len(responses_to_return) == 0:
        return NONE_RESPONSE
    response_text = ""
    for res in responses_to_return:
        response_text += res + "\n"
    return response_text

def deepseek_chat(message, history, json_result):
    
    response = client_deepseek.chat.completions.create(
        model = "deepseek-chat",
        messages = [
            {
                'role': 'user', 
                'content': PROMPT_TEMPLATE.format(message)
            }
        ],
        stream=False
    )
    
    response_text = response.choices[0].message.content
    
    # 匹配[...]的内容(包括中括号)
    results = re.findall(r'\[.*?\]', response_text)
    if len(results) == 0:
        return NONE_RESPONSE
    result = results[0]
    result = result[1:-1]
    result = result.split(",")
    result = [x.strip() for x in result]
    result = [x[1:-1] for x in result if '"' in x or "'" in x]
    result = [x.strip() for x in result]
    
    print(result)
    responses_to_return = []
    for category in result:
        if category == "None":
           continue
        res = response_of_category(category, json_result)
        if res:
            responses_to_return.append(res)
    
    if len(responses_to_return) == 0:
        return NONE_RESPONSE
    response_text = ""
    for res in responses_to_return:
        response_text += res + "\n"
    return response_text

def get_basic_info(json_result):
    responses_to_return = []
    res = response_of_category("apk_name", json_result)
    if res:
        responses_to_return.append(res)
    res = response_of_category("package_name", json_result)
    if res:
        responses_to_return.append(res)
    res = response_of_category("traffic_features", json_result)
    if res:
        responses_to_return.append(res)
    response_text = "## 分析结果\n"
    for res in responses_to_return:
        response_text += res + "\n"
    return response_text
    

def response_of_category(category, json_result):
    if category == "None":
        return None
    if category == "apk_name":
        response = f"应用名称：{json_result['static_info']['apk_name']}\n"
        return response
    if category == "package_name":
        response = f"包名：{json_result['static_info']['package_name']}\n"
        return response
    if category == "version_code":
        response = f"版本号：{json_result['static_info']['version_code']}\n"
        return response
    if category == "version_name":
        response = f"版本名称：{json_result['static_info']['version_name']}\n"
        return response
    if category == "permissions":
        if len(json_result['static_info']['permissions']) == 0:
            return "应用未申请任何权限"
        response = "应用申请的权限包括：\n"
        for item in json_result['static_info']['permissions']:
            response += f"\t{item}\n"
        return response
    if category == "activities":
        if len(json_result['static_info']['activities']) == 0:
            return "应用未包含任何Activity"
        response = "应用内的Activity包括：\n"
        for item in json_result['static_info']['activities']:
            response += f"\t{item}\n"
        return response
    if category == "min_sdk_version":
        response = f"最小SDK版本：{json_result['static_info']['min_sdk']}\n"
        return response
    if category == "target_sdk_version":
        response = f"目标SDK版本：{json_result['static_info']['target_sdk']}\n"
        return response
    if category == "traffic_features":
        if len(json_result['network_info']) == 0:
            return "应用未产生任何网络流量(请联系管理员检查代理配置或域名过滤配置)"
        response = "网络特征：\n"
        response += "| 首次请求时间 | 域名 | 端口 | IP | 协议 | IP位置信息 |\n"
        response += "| --- | --- | --- | --- | --- | --- |\n"
        for item in json_result['network_info']:
            response += f"| {item['timestamp']} | {item['domain_name']} | {item['port']} | {item['IP']} | {item['protocol']} | {item['ip_location']} |\n"
        return response
    return None

PROMPT_TEMPLATE_FILTER_DOMAIN = PROMPT_TEMPLATE_FILTER_DOMAIN = '''
Act as a cybersecurity and network traffic analysis expert specializing in application disruption. Strictly follow these analysis rules:

1. Input Structure:
   - App Name: [app_name]
   - Package Name: [package_name]
   - Domain List: [domain_list] (captured during dynamic testing with mitmproxy)

2. Core Objective:
   Identify critical domains/IPs whose blocking would disrupt PRIMARY application functionality by cutting off essential network communication.

3. Selection Criteria (ordered by priority):
   a) Domains containing app name or clear functional keywords
   b) Domains appearing earlier in domain sequence (domains are listed in order of access time) are more likely to be critical
   c) First-party API endpoints and authentication servers
   d) App-specific content delivery domains (even if CDN, if containing app name or seems quite specific)
   e) Domains with unique identifiers (e.g., app-specific subdomains)
   f) Domains with related keywords with app functionality mentioned in app name or package name

4. Exclusion Criteria (must filter out):
   - Generic third-party services (analytics/advertising/push)
   - Common cloud providers (aws.com, azure.com, etc.)
   - Generic CDNs without app-specific identifiers
   - OS/device manufacturer domains
   - Certificate revocation/OCSP services
   - Domians whose IP location is in China Mainland (not including Hong Kong, Macao, Taiwan)

5. Output Requirements:
   - One domain/IP per line
   - No numbering, punctuation or explanations
   - Prioritized order (most critical first)
   - Identical to the input domain which you picked

6. Validation Rules:
   - Each selected domain must pass: "If blocked, would this prevent core functionality?"
   - Must be able to justify selection by app context if audited

Example:
Input:
App Name: SecureChat
Package Name: com.securechat.prod
Domain List: [api.securechat.com, cdn.chatassets.com, stats.mobile.sdk, ocsp.digicert.com]

Output:
api.securechat.com
cdn.chatassets.com

Begin analysis:
App Name: {app_name}
Package Name: {package_name}
Domain List: {domain_list}
'''

def filter_domains_need_to_block(json_result,all_domains):
    app_name = json_result['static_info']['apk_name']
    package_name = json_result['static_info']['package_name']
    # 过滤掉不需要屏蔽的域名
    domains_to_block = []
    response = client_deepseek.chat.completions.create(
        model = "deepseek-chat",
        messages = [
            {
                'role': 'user', 
                'content': PROMPT_TEMPLATE_FILTER_DOMAIN.format(
                    app_name=app_name,
                    package_name=package_name,
                    domain_list=str(all_domains)
                )
            }
        ],
        stream=False
    )
    
    response_text = response.choices[0].message.content
    
    response_text = response_text.strip().split("\n")
    response_text = [x.strip() for x in response_text]
    response_text = [x for x in response_text if x]
    domains_to_block = [x for x in response_text if x in all_domains]
    
    return domains_to_block

def merge_to_second_level_domains(domains):
    """
    将域名列表合并为二级域名列表
    例如: ['api.example.com', 'cdn.example.com'] -> ['example.com']
    """
    second_level_domains = set()
    
    for domain in domains:
        try:
            extract_result = tldextract.extract(domain)
            if extract_result.subdomain:
                second_level_domain = extract_result.subdomain
                second_level_domains.add(second_level_domain)
        except Exception as e:
            logging.warning(f"解析域名失败: {domain}, 错误: {e}")
            # 如果解析失败，保留原域名
            second_level_domains.add(domain)
    
    return list(second_level_domains)
    
# if __name__ == '__main__':
#     # only for testing
#     TEST_JSON_RESULT = {"static_info": {"apk_name": "\u5f69\u7968\u5df4\u5df4", "package_name": "com.eprometheus.cp88", "version_code": "1", "version_name": "1.0", "permissions": ["android.permission.RECEIVE_BOOT_COMPLETED", "android.permission.VIBRATE", "android.permission.ACCESS_WIFI_STATE", "android.permission.POST_NOTIFICATIONS", "com.sec.android.provider.badge.permission.READ", "me.everything.badger.permission.BADGE_COUNT_READ", "android.permission.ACCESS_COARSE_LOCATION", "com.htc.launcher.permission.UPDATE_SHORTCUT", "com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE", "com.huawei.android.launcher.permission.CHANGE_BADGE", "com.huawei.android.launcher.permission.WRITE_SETTINGS", "android.permission.ACCESS_FINE_LOCATION", "com.huawei.android.launcher.permission.READ_SETTINGS", "com.android.vending.CHECK_LICENSE", "android.permission.READ_EXTERNAL_STORAGE", "android.permission.ACCESS_BACKGROUND_LOCATION", "android.permission.READ_PHONE_STATE", "com.anddoes.launcher.permission.UPDATE_COUNT", "com.sonyericsson.home.permission.BROADCAST_BADGE", "com.oppo.launcher.permission.READ_SETTINGS", "com.majeur.launcher.permission.UPDATE_BADGE", "com.sec.android.provider.badge.permission.WRITE", "android.permission.DOWNLOAD_WITHOUT_NOTIFICATION", "com.google.android.c2dm.permission.RECEIVE", "android.permission.WRITE_EXTERNAL_STORAGE", "android.permission.INTERNET", "com.vivo.notification.permission.BADGE_ICON", "android.permission.QUERY_ALL_PACKAGES", "com.sonymobile.home.permission.PROVIDER_INSERT_BADGE", "me.everything.badger.permission.BADGE_COUNT_WRITE", "com.htc.launcher.permission.READ_SETTINGS", "com.eprometheus.cp88.permission.JPUSH_MESSAGE", "android.permission.WAKE_LOCK", "com.oppo.launcher.permission.WRITE_SETTINGS", "android.permission.CAMERA", "android.permission.READ_APP_BADGE", "com.hihonor.android.launcher.permission.CHANGE_BADGE", "android.permission.ACCESS_NETWORK_STATE", "android.permission.GET_TASKS"], "activities": ["com.boilerplate69.SplashActivity", "com.boilerplate69.MainActivity", "pub.devrel.easypermissions.AppSettingsDialogHolderActivity", "com.facebook.react.devsupport.DevSettingsActivity", "com.google.android.gms.common.api.GoogleApiActivity", "com.umeng.message.component.UmengNotificationClickActivity", "com.umeng.message.notify.UPushMessageNotifyActivity", "cn.jpush.android.ui.PopWinActivity", "cn.jpush.android.ui.PushActivity", "cn.jpush.android.service.DActivity", "cn.jpush.android.service.JNotifyActivity", "cn.android.service.JTransitActivity"], "min_sdk": "21", "target_sdk": "31"}, "network_info": [{"domain_name": "dwdabw4r.xiduoshi.xyz", "port": "443", "IP": "61.48.83.208", "protocol": "https"}, {"domain_name": "beacons.gcp.gvt2.com", "port": "443", "IP": "114.250.63.34", "protocol": "https"}, {"domain_name": "cp88-fs.shouyiba.xyz", "port": "443", "IP": "61.48.83.217", "protocol": "https"}, {"domain_name": "cp88-fs.yyojzrnc.com", "port": "443", "IP": "170.33.0.252", "protocol": "https"}, {"domain_name": "update.googleapis.com", "port": "443", "IP": "114.250.65.34", "protocol": "https"}, {"domain_name": "cp88-fs.gojcuqjw.com", "port": "443", "IP": "118.107.11.2", "protocol": "https"}, {"domain_name": "edgedl.me.gvt1.com", "port": "80", "IP": "34.104.35.123", "protocol": "http"}, {"domain_name": "beacons5.gvt3.com", "port": "443", "IP": "114.250.67.34", "protocol": "https"}, {"domain_name": "cp88-fs.blzavkbm.com", "port": "443", "IP": "170.33.0.252", "protocol": "https"}, {"domain_name": "cp88-fs.fzqrfaxr.com", "port": "443", "IP": "170.33.0.252", "protocol": "https"}, {"domain_name": "cp88-fs.skrhfoahahf572.top", "port": "443", "IP": "61.48.83.208", "protocol": "https"}, {"domain_name": "cp88-fs.yixaznlc.com", "port": "443", "IP": "20.205.129.82", "protocol": "https"}, {"domain_name": "cp88-fs.prigufnq.com", "port": "443", "IP": "118.107.11.2", "protocol": "https"}]}
    
#     while True:
#         message = input("Enter your message: ")
#         print(ollama_chat(message, [], TEST_JSON_RESULT))