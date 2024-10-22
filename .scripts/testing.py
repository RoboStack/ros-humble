import run_patch_workflow as wf
import time
good_builds = 0
bad_builds = 0
time_storage = []
successful_build = True

for i in range(3):
    
    try:
        start_time = time.time()
        wf.run()
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

#This one is large script