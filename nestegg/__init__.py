class NesteggException(Exception): pass

def first(it) :
    try :
        return next(it)
    except StopIteration :
        return None

