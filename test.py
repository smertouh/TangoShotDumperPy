class A:
    def hi(self):
        print("A")


class B(A):
    def hi1(self):
        print("B")


class C(A):
    def h2i(self):
        print("C")


class D(B, C):
    def hi1(self):
        print("D")
    pass


d = D()
d.hi()