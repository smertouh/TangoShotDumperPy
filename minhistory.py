from ShotDumper import TangoAttribute
import time

class TangoAttributemin(TangoAttribute):
 def read_attribute(self):
  self.attr = self.devProxy.read_attribute(self.name)
  self.time = time.time()
  v1 = [c.value for c in self.devProxy.attribute_history(self.name, 100)]
  v2 = min(v1)
  self.attr.value = v2