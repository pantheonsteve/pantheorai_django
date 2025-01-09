from google.cloud import bigquery
from google.cloud import storage
import sys
import json
import datetime

PROJECT_ID = "pantheon-sales"
LOCATION = "us-central1"
BQ_DATASET = "gong"
BQ_TABLE = "call-data-complete"
SOURCE_BUCKET="pantheor_ai_data"

class GongGCS:

    '''
    The GongGCS interacts with the Gong call data that has been stored in Google Cloud Storage and Big Query.
    '''

    def __init__(self):
        self.storage_client = storage.Client(project=PROJECT_ID)
        self.bucket_name = "pantheor_ai_data"

    def call_metadata(self, call_id):
        # Initialize a BigQuery client
        client = bigquery.Client()

        # Define the query
        query = f"""
            SELECT
                `metaData`.`started`,
                `metaData`.`title`,
                `metaData`.`url`,
            FROM
                `pantheon-sales.gong.call-data-complete`
            WHERE
                `metaData`.`id` = '{call_id}';
            """

        # Execute the query
        query_job = client.query(query)

        # Process the results
        call = {}
        for row in query_job:
            call['started'] = row['started']
            call['title'] = row['title']
            call['url'] = row['url']
            return call
        return None


    # Move this to Gong GCS
    def call_transcript(self, call_id):
        """
        Retrieves the transcript text from a Google Cloud Storage bucket.

        Args:

            call_id: The ID of the call.

        Returns:

            The transcript text as a string, or None if the file is not found.
        """
        file_path = f"gong/calls/transcripts/{call_id}.txt"

        try:
            call = {}
            call_metadata = self.call_metadata(call_id)
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(file_path)
            transcript_text = blob.download_as_string().decode("utf-8")
            call['transcript'] = transcript_text
            call['call_id'] = call_id
            call['title'] = call_metadata['title']
            call['started'] = call_metadata['started']
            call['url'] = call_metadata['url']
            return call
        except Exception as e:
            print(f"Error retrieving transcript for call ID {call_id}: {e}")
            return None

    #get_transcript_text('7291216304130161099')

    def get_calls_by_opp(self, opp_id):
        """
        Fetches a list of call IDs from BigQuery where the given Opportunity ID matches.

        Args:
            opp_id (str): The Opportunity ID to search for.

        Returns:
            list: A list of call IDs.
        """
        # Initialize a BigQuery client
        client = bigquery.Client()

        # Define the query
        query = f"""
        SELECT DISTINCT
        `metaData`.`id` AS `call_id`,
        `objects`.`objectId` AS `opportunity_id`,
        `fields`.`value` AS `opportunity_name`
        FROM
        `pantheon-sales.gong.call-data-complete`,
        UNNEST(`context`) AS `context`,
        UNNEST(`context`.`objects`) AS `objects`,
        UNNEST(`objects`.`fields`) AS `fields`
        WHERE
        `objects`.`objectType` = 'Opportunity'
        AND `objects`.`objectId` = '{opp_id}'
        AND `fields`.`name` = 'Name';
        """

        # Execute the query
        query_job = client.query(query)

        # Process the results
        opportunity = {}
        opportunity['opportunity_name'] = [row['opportunity_name'] for row in query_job][0][0]
        opportunity['call_ids'] = [row['call_id'] for row in query_job]

        return opportunity

    def get_calls_by_account(self, account_id):
        """
        Fetches a list of call IDs from BigQuery where the given Opportunity ID matches.

        Args:
            opp_id (str): The Opportunity ID to search for.

        Returns:
            list: A list of call IDs.
        """
        # Initialize a BigQuery client
        client = bigquery.Client()

        # Define the query
        query = f"""
        SELECT DISTINCT
        `metaData`.`id` AS `call_id`,
        `objects`.`objectId` AS `account_id`,
        `fields`.`value` AS `account_name`
        FROM
        `pantheon-sales.gong.call-data-complete`,
        UNNEST(`context`) AS `context`,
        UNNEST(`context`.`objects`) AS `objects`,
        UNNEST(`objects`.`fields`) AS `fields`
        WHERE
        `objects`.`objectType` = 'Account'
        AND `objects`.`objectId` = '{account_id}'
        AND `fields`.`name` = 'Name';
        """

        # Execute the query
        query_job = client.query(query)

        account = {}
        account['account_name'] = [row['account_name'] for row in query_job][0][0]
        account['call_ids'] = [row['call_id'] for row in query_job]

        return account

    def collate_transcripts(self, call_ids):
        full_transcripts = ""
        for call_id in call_ids:
            transcript = self.call_transcript(call_id)
            if transcript:
                full_transcripts += str(transcript)
        return full_transcripts