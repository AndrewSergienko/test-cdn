import json
import os
from pathlib import Path
from typing import AsyncIterable, Callable

import aiofiles
from aiofiles import os as aios
from aiohttp import ClientSession

from src.abstract import adapters as abstract
from src.domain.model import FileInfo, ReplicatedFileStatus, Server


class WebClient(abstract.AWebClient):
    async def download_and_save_file(
        self, link: str, files_dir: Path, file_name: str, save_file_function: Callable
    ) -> FileInfo:
        async with ClientSession() as session:
            async with session.get(link) as resp:
                file_type = resp.content_type.split("/")[1]
                file_type = file_type if file_type != "octet-stream" else "bin"
                # Saving file
                await save_file_function(
                    files_dir, f"{file_name}.{file_type}", resp.content.iter_chunks()
                )
                return FileInfo(name=file_name, file_type=file_type, origin_url=link)

    async def upload_file(
        self, server: Server, file: FileInfo, test: bool = False
    ) -> dict:
        async with ClientSession() as session:
            data = {"content": file.content, "name": file.name, "type": file.file_type}
            async with session.post(f"http://{server.ip}:8080", data=data) as resp:
                return {"server": server, "status": resp.status}

    async def send_file_status(self, origin_url: str, status: ReplicatedFileStatus):
        async with ClientSession() as session:
            data = {
                "source_server": "",
                "target_server": {
                    "name": status.server.name,
                    "zone": status.server.zone,
                },
                "duration": status.duration,
                "time": status.time,
                "origin_file_url": status.origin_url,
            }
            async with session.post(origin_url, data=data):
                pass


class FileManager(abstract.AFileManager):
    async def save_file(
        self, files_dir: Path, file_name: str, chunk_iterator: AsyncIterable
    ) -> str:
        """
        Saving the file in the system.
        :param files_dir: dir of files
        :param file: bytes
        :return: file name
        """
        async with aiofiles.open(files_dir / file_name, "wb") as f:
            async for chunk in chunk_iterator:
                await f.write(chunk[0])
        return file_name

    async def delete_file(self, files_dir: Path, file_name: str):
        await aios.remove(files_dir / file_name)

    async def is_file_exists(self, files_dir: Path, file_name: str) -> bool:
        return await aios.path.exists(files_dir / file_name)


class EnvManager(abstract.AEnvManager):
    async def get(self, key: str) -> str:
        return os.environ.get(key)


class ServersManager(abstract.AServersManager):
    async def get_servers(self, root_dir: Path) -> list[Server]:
        with open(root_dir / "servers.json") as f:
            servers = json.load(f)
        return [
            Server(server["name"], server["ip"], server["zone"]) for server in servers
        ]
