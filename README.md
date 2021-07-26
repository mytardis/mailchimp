## Export user emails from MyTardis to Mailchimp

This script will collect emails for the list of active users and export it 
to a selected Mailchimp mail group (also known as segment).

We will support MyTardis version 4.5+

### Technical details

Settings are available through default setting.yaml config file.

You must specify credentials to the database and Mailchimp API. Please note 
that you have to provide list_id and segment_id for desired mail group in 
Mailchimp (in settings).

You can exclude any emails based on list of regex (see how we removed any 
emails from example.com domain in settings.yaml)

Run from command line:

```
python index.py [-h] [--config CONFIG] [--days DAYS]

optional arguments:
  --config CONFIG  Config file location.
  --days XX        Populate only users those logged in XX past days,
                   default is 0 to export all data.
```

### Docker and Kubernetes

We build automatically the latest version of Docker image and publish it on 
DockerHub with [mytardis/mailchimp:latest](https://hub.docker.com/r/mytardis/mailchimp) image name.

Sample files in [kubernetes](./kubernetes/) folder will provide you with 
example of running this script in Kubernetes.
