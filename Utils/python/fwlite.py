#!/usr/bin/env python3
from typing import Optional
from DataFormats.FWLite import Handle

class EDMObject:
    def __init__(self,
                 type: str,
                 module: str,
                 process_instance: Optional[str] = None,
                 process: Optional[str] = None) -> None:

        self._handle = Handle(type)

        label = [module, process_instance, process]
        self._label = tuple(each for each in label if each is not None)

        self._product = None
        self._objs = []

    def get(self, event):
        event.getByLabel(self._label, self._handle)
        return self._handle.product()

    def init(self, event):
        self._product = self.get(event)
        self._objs = [each for each in self._product]

    def __iter__(self):
        return iter(self._objs)

    def __len__(self):
        return len(self._objs)

    def __getitem__(self, index):
        return self._objs[index]

    @property
    def product(self):
        return self._product
