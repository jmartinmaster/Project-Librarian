import time

leaky_list = []

for i in range(100000):
    leaky_list.append(str(i) * 100)

print("Dummy leak executed.")
