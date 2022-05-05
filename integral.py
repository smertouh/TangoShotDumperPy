from ShotDumper import TangoAttribute
import time
import numpy as np

class TangoAttributeintegral(TangoAttribute):
 def read_attribute(self):
  pollrange=600
  pollrange1=100
  self.attr = self.devProxy.read_attribute(self.name)
  self.time = time.time()
  v1 = [c.value for c in self.devProxy.attribute_history(self.name, pollrange)]
  v2=0
  vmin=np.min(v1)
  for i in range(0,pollrange-pollrange1):
    v2=v2+v1[i]*0.2-vmin*0.2
  self.attr.value = v2
print("end")