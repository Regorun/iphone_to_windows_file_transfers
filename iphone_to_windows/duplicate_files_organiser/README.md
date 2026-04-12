# Duplicate file organiser

## Criteria:

-Match file names in existing folder and subfolder
-If match found, compare file size and move the smaller file to folder "duplicates-smaller_size"
-If match found with same file size, run a hash. If hash is same, move one file to folder "duplicates-smaller_size"
-Write to log file "log-find_duplicates.txt"


```
pyinstaller --console --onefile --name find_duplicates find_duplicates.py
```

**Build by Regorum Technologies**