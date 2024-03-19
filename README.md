```
create database survivor;
create table survivorLog (
  id SERIAL PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  season int NOT NULL,
  episode int NOT NULL,
  timestamp TIMESTAMP
);
create user jeff with encrypted password 'xxx';
grant all privileges on database survivor to jeff;
grant all privileges on survivorLog to jeff;
grant all ON survivorLog_id_seq to jeff;
```

```
export DB_HOST=192.168.0.3
export DB_DB=survivor
export DB_USER=jeff
export DB_PASS=xxxxx

export SIGNAL_API=http://192.168.254.11
export SIGNAL_FROM='+14808407117'
export SIGNAL_TO='+15159792049'
```
