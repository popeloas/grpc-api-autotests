"""gRPC-клиент: отправляет запрос как dict и возвращает ответ как dict.

Описание методов берётся у самого сервиса через server reflection (как в Postman / grpcurl),
поэтому .proto и сгенерированный код тестам не нужны."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import grpc
from google.protobuf import descriptor_pool, json_format, message_factory
from grpc_reflection.v1alpha.proto_reflection_descriptor_database import (
    ProtoReflectionDescriptorDatabase,
)


@dataclass
class GrpcError(Exception):
    method: str
    code: grpc.StatusCode
    details: str

    def __str__(self) -> str:
        return f"{self.method}: {self.code.name} — {self.details}"


class GrpcJsonClient:
    def __init__(self, target: str, timeout: float = 10.0, metadata: dict[str, str] | None = None):
        self.target = target
        self.timeout = timeout
        self.metadata = list((metadata or {}).items())
        self.channel = grpc.insecure_channel(target)
        self._db = ProtoReflectionDescriptorDatabase(self.channel)
        self._pool = descriptor_pool.DescriptorPool(self._db)

    # --- интроспекция (контрактные тесты) ---
    def services(self) -> list[str]:
        return sorted(self._db.get_services())

    def methods(self, service: str) -> list[str]:
        return sorted(m.name for m in self._pool.FindServiceByName(service).methods)

    def output_message(self, full_method: str):
        """Дескриптор ответа метода — для сверки pydantic-моделей с живой схемой сервиса."""
        service_name, method_name = full_method.split("/")
        return self._pool.FindServiceByName(service_name).methods_by_name[method_name].output_type

    # --- вызов ---
    def call(
        self,
        full_method: str,
        body: dict[str, Any] | None = None,
        *,
        metadata: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """full_method: 'package.Service/Method'. Для server-streaming возвращает список dict."""
        service_name, method_name = full_method.split("/")
        method = self._pool.FindServiceByName(service_name).methods_by_name[method_name]
        req_cls = message_factory.GetMessageClass(method.input_type)
        resp_cls = message_factory.GetMessageClass(method.output_type)
        request = json_format.ParseDict(body or {}, req_cls())
        path = f"/{service_name}/{method_name}"
        md = self.metadata + list((metadata or {}).items())
        kwargs = {"timeout": timeout or self.timeout, "metadata": md or None}
        try:
            if method.server_streaming:
                stub = self.channel.unary_stream(
                    path, request_serializer=req_cls.SerializeToString, response_deserializer=resp_cls.FromString
                )
                return [self._to_dict(m) for m in stub(request, **kwargs)]
            stub = self.channel.unary_unary(
                path, request_serializer=req_cls.SerializeToString, response_deserializer=resp_cls.FromString
            )
            return self._to_dict(stub(request, **kwargs))
        except grpc.RpcError as e:  # noqa: PERF203
            raise GrpcError(full_method, e.code(), e.details()) from None

    @staticmethod
    def _to_dict(msg) -> dict[str, Any]:
        return json_format.MessageToDict(
            msg, preserving_proto_field_name=True, always_print_fields_with_no_presence=True
        )

    def close(self) -> None:
        self.channel.close()
