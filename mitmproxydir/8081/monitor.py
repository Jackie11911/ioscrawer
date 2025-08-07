import os
import time
import socket

import mitmproxy.http

import logging

class Counter:
    def __init__(self):
        self.sessions = {}  # 用于跟踪会话的字典
        self.request_count = 0  # 请求计数器
        self.response_count = 0  # 响应计数器
        self.error_log_file_all = ""  # 总报错日志文件路径
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(self.current_dir, "log", "requests")
    
    def load(self, loader):
        os.makedirs(self.log_dir, exist_ok=True)
        
        error_log_file_name = f"{time.strftime('%Y%m%d')}_error_log.txt"
        self.error_log_file_all = os.path.join(self.log_dir, error_log_file_name)

        
    def request(self, flow: mitmproxy.http.HTTPFlow):
        # 记录请求时间戳
        flow.metadata["request_timestamp"] = time.time()
        
        if "session_id" not in flow.metadata:
            session_id = self.get_session_id()
            self.sessions[flow] = self.create_session_dir(session_id)
            flow.metadata["session_id"] = session_id
        
        session_dir = self.sessions[flow]
        
        # Save request body
        request_body_file = os.path.join(session_dir, "request_body.txt")
        with open(request_body_file, mode="wb") as f:
            if flow.request.content:
                try:
                    f.write(flow.request.content)
                except UnicodeDecodeError as e:
                    self.log_error(session_dir, flow, "request", str(e))

        # Save headers
        headers_file = os.path.join(session_dir, "headers.txt")
        with open(headers_file, mode="w", encoding="UTF-8") as f:
            f.write(f"{flow.request.method} {flow.request.url}\n")
            for name, value in flow.request.headers.items():
                f.write(f"{name}: {value}\n")
            f.write("\n\n")
            
        # 创建metadata.txt，写入手机端的ip、端口，服务器域名、ip、端口等信息
        # 获取连接信息
        client_address = flow.client_conn.address
        client_address_str = f"{client_address[0]}:{client_address[1]}"
        
        server_address = flow.server_conn.address
        server_address_str = f"{server_address[0]}:{server_address[1]}"
        server_resolved_address = socket.gethostbyname(server_address[0])  # 获取服务器解析后的地址信息

        # 将连接信息写入文件
        metadata_file = os.path.join(session_dir, "metadata.txt")
        with open(metadata_file, mode="w", encoding="UTF-8") as f:
            # 加一个时间戳 年月日时分秒
            f.write(f"Timestamp:\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Client Connection\n")
            f.write("Address:\t" + client_address_str + "\n\n")
            f.write("Server Connection\n")
            f.write("Address:\t" + server_address_str + "\n")
            f.write("Resolved address:\t" + server_resolved_address + "\n\n")
        
        # 增加请求计数
        self.request_count += 1

    def response(self, flow: mitmproxy.http.HTTPFlow):
        session_dir = self.sessions.get(flow, None)
        if session_dir is None:
            return
        
        # 保存响应时间戳
        flow.metadata["response_timestamp"] = time.time()
        
        # Save response body
        response_body_file = os.path.join(session_dir, "response_body.txt")
        with open(response_body_file, mode="wb") as f:
            if flow.response.content:
                try:
                    f.write(flow.response.content)
                except UnicodeDecodeError as e:
                    self.log_error(session_dir, flow, "response", str(e))

        # Append response headers to existing headers file
        headers_file = os.path.join(session_dir, "headers.txt")
        with open(headers_file, mode="a", encoding="UTF-8") as f:
            f.write(f"\n\n{flow.response.http_version} {flow.response.status_code} {flow.response.reason}\n")
            for name, value in flow.response.headers.items():
                f.write(f"{name}: {value}\n")

        # 创建metadata.txt，写入手机端的ip、端口，服务器域名、ip、端口等信息
        # 获取连接信息
        client_address = flow.client_conn.address
        client_address_str = f"{client_address[0]}:{client_address[1]}"
        
        server_address = flow.server_conn.address
        server_address_str = f"{server_address[0]}:{server_address[1]}"
        server_resolved_address = socket.gethostbyname(server_address[0])  # 获取服务器解析后的地址信息

        # 将连接信息写入文件
        metadata_file = os.path.join(session_dir, "metadata.txt")
        with open(metadata_file, mode="w", encoding="UTF-8") as f:
            # 加一个时间戳 年月日时分秒
            f.write(f"Timestamp:\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Client Connection\n")
            f.write("Address:\t" + client_address_str + "\n\n")
            f.write("Server Connection\n")
            f.write("Address:\t" + server_address_str + "\n")
            f.write("Resolved address:\t" + server_resolved_address + "\n\n")
        
        # 增加响应计数
        self.response_count += 1
        
    def server_connect(self, conn: mitmproxy.proxy.server_hooks.ServerConnectionHookData):
        
        session_id = self.get_session_id()
        session_dir = self.create_session_dir(session_id)
        
        server_domain = conn.server.address[0]
        server_port = conn.server.address[1]
        server_resolved_address = socket.gethostbyname(server_domain)
        
        # Save metadata
        with open(os.path.join(session_dir, "metadata.txt"), mode="w", encoding="UTF-8") as f:
            # 加一个时间戳 年月日时分秒
            f.write(f"Timestamp:\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Server Connection\n")
            f.write(f"Address:\t{server_domain}:{server_port}\n")
            f.write(f"Resolved address:\t{server_resolved_address}\n\n")
            
        with open(os.path.join(session_dir, "headers.txt"), mode="w", encoding="UTF-8") as f:
            f.write(f"GET https://{server_domain}:{server_port}/ HTTP/1.1\n")

    # def tcp_start(self, flow: mitmproxy.tcp.TCPFlow):
    #     session_id = self.get_session_id()
    #     session_dir = self.create_session_dir(session_id)
    #     flow.metadata["session_id"] = session_id
    #     self.sessions[flow] = session_dir

    #     client_address = flow.client_conn.address
    #     client_address_str = f"{client_address[0]}:{client_address[1]}"
        
    #     server_address = flow.server_conn.address
    #     server_address_str = f"{server_address[0]}:{server_address[1]}"
    #     server_resolved_address = socket.gethostbyname(server_address[0])

    #     metadata_file = os.path.join(session_dir, "metadata.txt")
    #     with open(metadata_file, mode="w", encoding="UTF-8") as f:
    #         f.write("TCP Connection Start\n")
    #         f.write("Client Connection\n")
    #         f.write("Address:\t" + client_address_str + "\n\n")
    #         f.write("Server Connection\n")
    #         f.write("Address:\t" + server_address_str + "\n")
    #         f.write("Resolved address:\t" + server_resolved_address + "\n\n")
            
    #     headers_file = os.path.join(session_dir, "headers.txt")
    #     with open(headers_file, mode="w", encoding="UTF-8") as f:
    #         f.write(f"TCP Connection Start\n")
    #         f.write("Client Connection\n")
    #         f.write("Address:\t" + client_address_str + "\n\n")
    #         f.write("Server Connection\n")
    #         f.write("Address:\t" + server_address_str + "\n")
    #         f.write("Resolved address:\t" + server_resolved_address + "\n\n")

    def log_error(self, session_dir, flow, flow_type, error_message):
        error_log_file = os.path.join(session_dir, "error_log.txt")
        with open(error_log_file, mode="a", encoding="UTF-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {flow.metadata['session_id']}  {flow_type}\n")
            f.write(f"{error_message}\n\n")
        
        with open(self.error_log_file_all, mode="a", encoding="UTF-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {flow.metadata['session_id']}  {flow_type}\n")
            f.write(f"{error_message}\n\n")

    def get_session_id(self):

        session_folders = os.listdir(self.log_dir)
        session_id = len(session_folders) + 1
        
        session_dir = os.path.join(self.log_dir, str(session_id))
        os.makedirs(session_dir, exist_ok=True)
        
        return session_id

    def create_session_dir(self, session_id):
        session_dir = os.path.join(self.log_dir, str(session_id))
        os.makedirs(session_dir, exist_ok=True)
        
        return session_dir





addons = [
    Counter()
]