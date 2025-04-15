
def get_version():
    """
    Returns the current version of the application.
    """
    with open("VERSION", "r") as file:
        VERSION = file.read().strip()
    return VERSION