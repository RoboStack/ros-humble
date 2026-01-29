"""Multipart form utils."""
import typing

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

if typing.TYPE_CHECKING:
    import tqdm


def multipart_files_upload(
        url: str,
        data: typing.MutableMapping,
        files: typing.Optional[typing.Mapping[str, tuple]] = None,
        progress_bar: typing.Optional['tqdm.tqdm'] = None,
        **request_kwargs: typing.Any) -> requests.Response:
    """
    Uploads one or more files as a multipart form.

    :param url: The URL to which the files will be uploaded.
    :param data: Dictionary, list of tuples, bytes, or file-like object to send in as a multipart form.
    :param files: Dictionary of ``{'name': file-tuple}`` for multipart encoding upload.
    :param progress_bar: An optional progress bar to display the upload progress.
    :param request_kwargs: Any additional keyword arguments to pass to the `requests.post()` function.

    """
    if files:
        data.update(files)

    encoder = MultipartEncoder(data)

    if progress_bar:
        encoder = MultipartEncoderMonitor(
            encoder, lambda monitor: progress_bar.update(monitor.bytes_read - progress_bar.n)
        )

    return requests.post(
        url,
        data=encoder,
        headers={'Content-Type': encoder.content_type},
        timeout=request_kwargs.pop('timeout', 10 * 60 * 60),
        **request_kwargs,
    )
