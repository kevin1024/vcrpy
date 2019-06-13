# coding: UTF-8
import io

from vcr.stubs import VCRHTTPResponse


def test_response_should_have_headers_field():
    recorded_response = {
        "status": {
            "message": "OK",
            "code": 200
        },
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "access-control-allow-credentials": ["true"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "access-control-allow-origin": ["*"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers is not None


def test_response_headers_should_be_equal_to_msg():
    recorded_response = {
        "status": {
            "message": b"OK",
            "code": 200
        },
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers == response.msg


def test_response_headers_should_have_correct_values():
    recorded_response = {
        "status": {
            "message": "OK",
            "code": 200
        },
        "headers": {
            "content-length": ["10806"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers.get('content-length') == "10806"
    assert response.headers.get('date') == "Fri, 24 Oct 2014 18:35:37 GMT"


def test_response_parses_correctly_and_fp_attribute_error_is_not_thrown():
    """
    Regression test for https://github.com/kevin1024/vcrpy/issues/440
    :return:
    """
    recorded_response = {
        "status": {
            "message": "OK",
            "code": 200
        },
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "access-control-allow-credentials": ["true"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "access-control-allow-origin": ["*"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b"\nPMID- 19416910\nOWN - NLM\nSTAT- MEDLINE\nDA  - 20090513\nDCOM- 20090622\nLR  - "
                      b"20141209\nIS  - 1091-6490 (Electronic)\nIS  - 0027-8424 (Linking)\nVI  - 106\nIP  - "
                      b"19\nDP  - 2009 May 12\nTI  - Genetic dissection of histone deacetylase requirement in "
                      b"tumor cells.\nPG  - 7751-5\nLID - 10.1073/pnas.0903139106 [doi]\nAB  - Histone "
                      b"deacetylase inhibitors (HDACi) represent a new group of drugs currently\n      being "
                      b"tested in a wide variety of clinical applications. They are especially\n      effective "
                      b"in preclinical models of cancer where they show antiproliferative\n      action in many "
                      b"different types of cancer cells. Recently, the first HDACi was\n      approved for the "
                      b"treatment of cutaneous T cell lymphomas. Most HDACi currently in\n      clinical "
                      b"development act by unspecifically interfering with the enzymatic\n      activity of all "
                      b"class I HDACs (HDAC1, 2, 3, and 8), and it is widely believed\n      that the development "
                      b"of isoform-specific HDACi could lead to better therapeutic\n      efficacy. The "
                      b"contribution of the individual class I HDACs to different disease\n      states, however, "
                      b"has so far not been fully elucidated. Here, we use a genetic\n      approach to dissect "
                      b"the involvement of the different class I HDACs in tumor\n      cells. We show that "
                      b"deletion of a single HDAC is not sufficient to induce cell\n      death, but that HDAC1 "
                      b"and 2 play redundant and essential roles in tumor cell\n      survival. Their deletion "
                      b"leads to nuclear bridging, nuclear fragmentation, and\n      mitotic catastrophe, "
                      b"mirroring the effects of HDACi on cancer cells. These\n      findings suggest that "
                      b"pharmacological inhibition of HDAC1 and 2 may be sufficient\n      for anticancer "
                      b"activity, providing an experimental framework for the development \n      of "
                      b"isoform-specific HDAC inhibitors.\nFAU - Haberland, Michael\nAU  - Haberland M\nAD  - "
                      b"Department of Molecular Biology, University of Texas Southwestern Medical Center,"
                      b"\n      5323 Harry Hines Boulevard, Dallas, TX 75390-9148, USA.\nFAU - Johnson, "
                      b"Aaron\nAU  - Johnson A\nFAU - Mokalled, Mayssa H\nAU  - Mokalled MH\nFAU - Montgomery, "
                      b"Rusty L\nAU  - Montgomery RL\nFAU - Olson, Eric N\nAU  - Olson EN\nLA  - eng\nPT  - "
                      b"Journal Article\nPT  - Research Support, N.I.H., Extramural\nPT  - Research Support, "
                      b"Non-U.S. Gov't\nDEP - 20090429\nPL  - United States\nTA  - Proc Natl Acad Sci U S A\nJT  "
                      b"- Proceedings of the National Academy of Sciences of the United States of America\nJID - "
                      b"7505876\nRN  - 0 (Antineoplastic Agents)\nRN  - 0 (Histone Deacetylase Inhibitors)\nRN  - "
                      b"0 (Protein Isoforms)\nRN  - EC 3.5.1.98 (Histone Deacetylases)\nSB  - IM\nMH  - "
                      b"Animals\nMH  - Antineoplastic Agents/pharmacology\nMH  - Cell Death\nMH  - Cell Line, "
                      b"Tumor\nMH  - Cell Survival\nMH  - Gene Expression Regulation, Enzymologic\nMH  - Gene "
                      b"Expression Regulation, Neoplastic\nMH  - Histone Deacetylase Inhibitors\nMH  - Histone "
                      b"Deacetylases/*genetics/*physiology\nMH  - Humans\nMH  - Mice\nMH  - Mice, Nude\nMH  - "
                      b"Models, Genetic\nMH  - Neoplasm Transplantation\nMH  - Neoplasms/metabolism\nMH  - "
                      b"Protein Isoforms\nPMC - PMC2683118\nOID - NLM: PMC2683118\nEDAT- 2009/05/07 09:00\nMHDA- "
                      b"2009/06/23 09:00\nCRDT- 2009/05/07 09:00\nAID - 0903139106 [pii]\nAID - "
                      b"10.1073/pnas.0903139106 [doi]\nPST - ppublish\nSO  - Proc Natl Acad Sci U S A. 2009 May "
                      b"12;106(19):7751-5. doi:\n      10.1073/pnas.0903139106. Epub 2009 Apr 29.\n "
        }
    }
    vcr_response = VCRHTTPResponse(recorded_response)
    handle = io.TextIOWrapper(io.BufferedReader(vcr_response), encoding='utf-8')
    handle = iter(handle)
    articles = [line for line in handle]
    assert len(articles) > 1
