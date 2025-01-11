
def update_object_data(obj, attribute_name, value) -> bool:
    if getattr(obj, attribute_name) != value:
        setattr(obj, attribute_name, value)
        return True
    return False