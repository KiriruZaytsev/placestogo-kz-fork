import os
import sys

import grpc

# NOTE(vladeemerr): Hack for gRPC-generated Python code to import its own artifacts
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))

import bot_backend_pb2_grpc

bot_backend_channel = grpc.insecure_channel("localhost:50051")
bot_backend_stub = bot_backend_pb2_grpc.BotBackendStub(bot_backend_channel)

logger = None
bot = None

