# Hadoop DataNode Connection Refused Runbook

## Symptoms
- DataNode connection refused
- Job execution timeout
- HDFS read/write failures

## Detection
Common log messages:
- Connection refused
- DataNode unavailable
- Failed to connect to DataNode
- SocketTimeoutException

## Possible Causes
1. DataNode service stopped
2. Firewall blocking RPC port
3. Network partition
4. Disk failure
5. Full disk
6. NameNode cannot reach DataNode

## Investigation Steps
1. Check DataNode process
2. Verify network connectivity
3. Review DataNode logs
4. Check disk usage
5. Verify NameNode reports

## Useful Commands
hdfs dfsadmin -report
hdfs fsck /
hdfs dfsadmin -printTopology

## Remediation
- Restart DataNode
- Replace failed disk
- Restore network connectivity
- Recommission DataNode