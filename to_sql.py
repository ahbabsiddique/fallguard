import pandas as pd
d = pd.read_csv("activity_log.csv")
vals = ",\n".join(f"('{r.TS}','{r.ROOM}','{r.ACTIVITY}',{r.CONFIDENCE},{r.IS_FALL})" for r in d.itertuples())
print("INSERT INTO FALLGUARD.APP.ACTIVITY_LOG VALUES\n" + vals + ";")
