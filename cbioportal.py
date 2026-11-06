#!/usr/bin/env python3

import argparse
import requests
import csv


BASE_URL = "https://www.cbioportal.org/api"

#############################
#Usage example:
#python cbioportal.py "coad" -o "coadsamples.tsv"
#
###############################################


def get_json(endpoint, params=None):
    url = BASE_URL + endpoint

    response = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json"},
        timeout=60
    )

    response.raise_for_status()
    return response.json()


def find_cancer_type(cancer_input):
    cancer_types = get_json("/cancer-types")

    query = cancer_input.lower()

    # Match cancer type ID or exact cancer type name
    exact = [
        x for x in cancer_types
        if x.get("cancerTypeId", "").lower() == query
        or x.get("name", "").lower() == query
    ]

    if len(exact) == 1:
        return exact[0]

    # Try partial matching against the cancer type name
    partial = [
        x for x in cancer_types
        if query in x.get("name", "").lower()
    ]

    if len(partial) == 1:
        return partial[0]

    if len(partial) > 1:
        print(f"Multiple cancer types match '{cancer_input}':")
        for x in partial:
            print(f"  {x['cancerTypeId']}\t{x['name']}")
        raise SystemExit(1)

    raise ValueError(
        f"No cBioPortal cancer type found matching: {cancer_input}"
    )


def get_sample_oncotree_codes(study_id):
    """
    Get the sample-level ONCOTREE_CODE values for a study.

    Returns a dictionary like:

        {
            "SAMPLE_001": "COAD",
            "SAMPLE_002": "COAD",
            "SAMPLE_003": "READ"
        }
    """

    clinical_data = get_json(
        f"/studies/{study_id}/clinical-data",
        params={
            "clinicalDataType": "SAMPLE",
            "projection": "SUMMARY",
            "pageSize": 10000000
        }
    )

    oncotree_codes = {}

    for record in clinical_data:

        if record.get("clinicalAttributeId") == "ONCOTREE_CODE":

            sample_id = record["sampleId"]
            oncotree_code = record["value"]

            oncotree_codes[sample_id] = oncotree_code

    return oncotree_codes


def get_samples_for_cancer(cancer_input):

    cancer = find_cancer_type(cancer_input)

    cancer_id = cancer["cancerTypeId"]
    cancer_name = cancer["name"]

    target_oncotree_code = cancer_id.upper()

    print(
        f"Cancer type: {cancer_name} "
        f"({cancer_id})"
    )

    print(
        f"Filtering samples for OncoTree code: "
        f"{target_oncotree_code}"
    )

    # Get all studies
    studies = get_json(
        "/studies",
        params={
            "projection": "SUMMARY",
            "pageSize": 10000000
        }
    )

    # Keep studies belonging to the requested cancer type
    matching_studies = [
        study for study in studies
        if study.get("cancerTypeId") == cancer_id
    ]

    print(f"Studies found: {len(matching_studies)}")

    rows = []

    for study in matching_studies:

        study_id = study["studyId"]

        print(
            f"\nGetting samples: {study['studyId']} | "
            f"{study['name']} | "
            f"cancerTypeId={study['cancerTypeId']} | "
            f"samples={study.get('allSampleCount')}"
        )

        # Get all samples in the study
        samples = get_json(
            f"/studies/{study_id}/samples",
            params={
                "projection": "SUMMARY",
                "pageSize": 10000000
            }
        )

        # Get the sample-level OncoTree codes
        oncotree_codes = get_sample_oncotree_codes(study_id)

        kept = 0

        for sample in samples:

            sample_id = sample["sampleId"]

            # Look up this sample's individual OncoTree code
            oncotree_code = oncotree_codes.get(sample_id)

            # Skip samples that are not the requested cancer type
            if oncotree_code != target_oncotree_code:
                continue

            rows.append({
                "Cancer Type": cancer_name,
                "Patient ID": sample["patientId"],
                "Sample ID": sample_id,
                "Study ID": study_id,
                "OncoTree Code": oncotree_code
            })

            kept += 1

        print(
            f"  {target_oncotree_code} samples kept: "
            f"{kept} / {len(samples)}"
        )

    return rows


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Get cBioPortal samples for a cancer type "
            "and filter by sample-level OncoTree code"
        )
    )

    parser.add_argument(
        "cancer_type",
        help='Cancer type, e.g. "Colon Adenocarcinoma" or "coad"'
    )

    parser.add_argument(
        "-o",
        "--output",
        default="cbioportal_samples.tsv"
    )

    args = parser.parse_args()

    rows = get_samples_for_cancer(args.cancer_type)

    with open(args.output, "w", newline="") as out:

        writer = csv.DictWriter(
            out,
            fieldnames=[
                "Cancer Type",
                "Patient ID",
                "Sample ID",
                "Study ID",
                "OncoTree Code"
            ],
            delimiter="\t"
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSamples found: {len(rows)}")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
