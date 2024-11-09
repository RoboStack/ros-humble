import run_patch_workflow as wf
import time
good_builds = 0
bad_builds = 0
time_storage = []
itemizied_time_storage = []
successful_build = True

for i in range(10):
    print(f"RUN {i}")
    try:
        start_time = time.time()
        timings = wf.run()
        itemizied_time_storage.append(timings)
        end_time = time.time()
        generation_time = end_time - start_time
        time_storage.append(generation_time)
    except Exception:
        successful_build = False

    if successful_build:
        good_builds += 1
    else:
        bad_builds += 1
    successful_build = True


print(f"Good Builds: {good_builds}")
print(f"Bad Builds: {bad_builds}")
average_time = sum(time_storage) / len(time_storage)
print(f"Average build time : {average_time}")

for timing, build in zip(itemizied_time_storage,range(len(itemizied_time_storage))):
    start_1 = timing[0]
    start_2 = timing[1]
    start_3 = timing[2]
    start_4 = timing[3]
    start_5 = timing[4]
    start_6 = timing[5]
    start_7 = timing[6]
    start_8 = timing[7]
    start_9 = timing[8]

    timing[0] = start_1
    print(F"RUN : {build}")
    print(f"Build 1 : {round(start_3-start_2)}, Script Retrieval : {round(start_6-start_5)}, AI Repair : {round(start_7 - start_6)}")
    print(f"Patch Generation : {round(start_8-start_7)}, Build 2 : {round(start_9-start_8)}")

#This one is large script