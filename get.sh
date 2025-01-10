#!/bin/bash
if [ -f venv/bin/activate ]; then
  . venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
  . venv/Scripts/activate
else
  echo "No virtual env"
  exit 1
fi

echo "* Get Performers from Stash box"
python get_performer_stashbox.py \
    -s "stash db" \
    -p a2749ba6-72d5-4165-a5e6-953c7a7d18f3 c4764f91-bfd2-4f7e-8a2b-b2392bb2c05e  4b46fc28-e257-45a9-ade6-22089c9f13e9

echo
echo "* Get Performers from fansdb"
python get_performer_stashbox.py \
    -s "fansdb" \
    -p 1f9d5468-bb5f-4796-bafe-1eb11434953f f1f7add2-6940-4b4a-affa-66643f8b1481
