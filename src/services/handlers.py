import asyncio
from datetime import datetime

from src.abstract.context import AContext
from src.domain import events
from src.domain.events import FileReplicatedEvent, FileSavedEvent


async def replicate_file(context: AContext, event: FileSavedEvent):
    """
    Replication saved file to servers
    :param context: Context instance
    :param event: file saved event
    """
    servers = await context.servers.get_servers(context.ROOT_DIR)
    # create uploading tasks
    tasks = [
        context.web.upload_file(server, event.file_info, event.chunk_iterator)
        for server in servers
    ]
    start_time = datetime.now()
    for task in asyncio.as_completed(tasks):
        # get result of finished task
        result = await task
        # get the task execution time
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        event = events.FileReplicatedEvent(
            event.file_info, duration, end_time, result["server"]
        )
        # run event handlers
        await context.events.publish(context, event)


async def send_saved_file_status(context: AContext, event: FileSavedEvent):
    """
    Send a message to the origin server about the successful saving of the file.
    :param context: Context instance
    :param event: file saved event
    """
    files_url = await context.env.get("FILES_URL")
    status = get_status_from_event(event, files_url)
    await context.web.send_file_status(await context.env.get("ORIGIN_URL"), status)


async def send_replicated_file_status(context: AContext, event: FileReplicatedEvent):
    """
    Send a message to the origin server about the successful replication of the file.
    :param context: Context instance
    :param event: file replicated event
    """
    files_url = await context.env.get("FILES_URL")
    status = get_status_from_event(event, files_url)
    status["server"] = {"name": event.server.name, "zone": event.server.zone}
    await context.web.send_file_status(await context.env.get("ORIGIN_URL"), status)


def get_status_from_event(
    event: FileReplicatedEvent | FileSavedEvent, files_url: str
) -> dict:
    file_name = f"{event.file_info.name}.{event.file_info.file_type}"
    return {
        "file_url": f"{files_url}/files/{file_name}",
        "origin_url": event.file_info.origin_url,
        "duration": event.duration,
        "time": event.time.strftime("%Y-%M-%D %H-%m-%S"),
    }


EVENT_HANDLERS = {
    events.FileSavedEvent: [replicate_file, send_saved_file_status],
    events.FileReplicatedEvent: [send_replicated_file_status],
}
