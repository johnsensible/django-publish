
class NestedSet(object):
    '''
        a class that can be used a bit like a set,
        but will let us store hiearchy too
    '''
    
    def __init__(self):
        self._root_elements = []
        self._children = {}
    
    def add(self, item, parent=None):
        if parent is None:
            self._root_elements.append(item)
        else:
            self._children[parent].append(item)
        self._children[item]=[]

    def __contains__(self, item):
        return item in self._children
    
    def __len__(self):
        return len(self._children)
    
    def _add_nested_items(self, items, nested):
        for item in items:
            nested.append(item)
            children = self._nested_children(item)
            if children:
                nested.append(children)

    def _nested_children(self, item):
        children = []
        self._add_nested_items(self._children[item], children)
        return children

    def nested_items(self):
        items = []
        self._add_nested_items(self._root_elements, items)
        return items
