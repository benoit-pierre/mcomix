"""file_tools.py - Contains various file helper functions."""

from mcomix import (
    archive_tools,
    image_tools,
)

def _get_archive_content_type(path):
    return archive_tools.archive_mime_type(path)

def _get_image_content_type(path):
    info = image_tools.get_image_info(path)
    # If one of the dimensions is 0, not an image.
    if 0 in info[1:]:
        return None
    return info[0]

def get_file_type(path, content_check=True, strict=False):
    file_class = None
    # Archive extension check.
    if archive_tools.is_archive_file(path):
        file_class = 'archive'
    # Image extension check.
    elif image_tools.is_image_file(path):
        file_class = 'image'
    # Check content if enabled.
    if content_check:
        # Note: check for an image first (if class was not set),
        # to avoid TAR format false positive on null content.
        check_list = ['image', 'archive']
        if file_class is not None:
            if strict:
                check_list.remove(file_class)
                check_list.insert(0, file_class)
            else:
                check_list = [file_class]
        for check_type in check_list:
            if 'archive' == check_type:
                check_fn = _get_archive_content_type
            elif 'image' == check_type:
                check_fn = _get_image_content_type
            file_type = check_fn(path)
            if file_type is not None:
                file_class = check_type
                break
            if strict:
                file_class = None
    else:
        file_type = None
    return file_class, file_type

# vim: expandtab:sw=4:ts=4
