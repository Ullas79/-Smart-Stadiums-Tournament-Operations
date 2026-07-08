"""Static knowledge documents for the RAG layer.

These cover FAQs, stadium policies, and amenity information that the agent
should retrieve (rather than invent) when answering fan questions.
"""
from __future__ import annotations

KNOWLEDGE_DOCS: list[dict[str, str]] = [
    {
        "id": "faq-bags",
        "title": "Bag policy",
        "text": (
            "MetLife Stadium enforces a clear-bag policy for the FIFA World Cup 2026 "
            "Final. Bags must be clear plastic, vinyl, or PVC and no larger than 30cm x 30cm x 15cm. "
            "Small clutches are permitted. Exceptions apply for medical needs."
        ),
    },
    {
        "id": "faq-gates-open",
        "title": "Gate opening times",
        "text": (
            "Gates open 90 minutes before kickoff for the World Cup Final. Arrive early; "
            "queues peak in the 30 minutes before kickoff. The Meadowlands Rail Station "
            "is the recommended transit option."
        ),
    },
    {
        "id": "faq-prohibited",
        "title": "Prohibited items",
        "text": (
            "Prohibited items include outside food and drink, weapons, noisemakers, laser pointers, "
            "professional cameras, and umbrellas. Smoking and vaping are not permitted anywhere "
            "in the seating bowl or concourses."
        ),
    },
    {
        "id": "faq-accessibility",
        "title": "Accessibility services",
        "text": (
            "MetLife Stadium offers accessible seating, elevator access to all levels, assistive "
            "listening devices, and sensory-inclusive kits at first-aid stations. Service animals "
            "are welcome. Accessible routes use elevators and ramps; escalators are not accessible."
        ),
    },
    {
        "id": "faq-first-aid",
        "title": "First aid",
        "text": (
            "First-aid stations are located on the North and South main concourses (C-L-N and C-L-S). "
            "For emergencies, notify the nearest volunteer or use any first-aid station."
        ),
    },
    {
        "id": "faq-water",
        "title": "Water stations",
        "text": (
            "Free water refill stations are available on every main concourse. Reusable empty "
            "bottles are permitted through gates."
        ),
    },
    {
        "id": "faq-wifi",
        "title": "Wi-Fi and connectivity",
        "text": (
            "Free stadium Wi-Fi is available network 'MetLife-Stadium-Free'. Multilingual "
            "assistance is available through the smart assistant in 30+ languages."
        ),
    },
    {
        "id": "faq-transit-rail",
        "title": "Rail transit",
        "text": (
            "NJ Transit Meadowlands Rail Station connects to Secaucus Junction, with service from "
            "New York Penn Station and points across New Jersey. Trains run frequently before and "
            "after the match; expect high demand after full-time."
        ),
    },
    {
        "id": "faq-transit-bus",
        "title": "Bus transit",
        "text": (
            "Coach USA express buses run from NYC Port Authority to the East Gate bus terminal. "
            "Service increases post-match but queues can reach 20 minutes."
        ),
    },
    {
        "id": "faq-parking",
        "title": "Parking",
        "text": (
            "Parking lots (N, S, E, W) open 4 hours before kickoff and require a pre-purchased pass. "
            "Tailgating is permitted in designated areas only. Ride-share pickup is at Lot W."
        ),
    },
    {
        "id": "faq-concessions",
        "title": "Concessions",
        "text": (
            "Concessions on every concourse serve food and non-alcoholic drinks. Alcohol sales end "
            "at the 70th minute. Vegetarian and halal options are available at the North and South "
            "main concourse concessions."
        ),
    },
    {
        "id": "faq-restrooms",
        "title": "Restrooms",
        "text": (
            "Restrooms are located on every concourse. The least crowded restrooms during peak times "
            "are typically on the East and West upper concourses. Use the assistant to check live "
            "crowd density near a restroom before you go."
        ),
    },
    {
        "id": "policy-incident",
        "title": "Incident reporting policy",
        "text": (
            "Volunteers and organizers may report incidents (medical, congestion, lost child, entry "
            "bottleneck) through the assistant. Provide type, location, and severity. Organizers "
            "receive decision-support recommendations and may manage crowd flow by opening secondary "
            "gates."
        ),
    },
    {
        "id": "policy-crowd-flow",
        "title": "Crowd flow management",
        "text": (
            "When a gate queue exceeds 12 minutes, the gate is marked restricted and fans should be "
            "rerouted to the nearest open gate. At halftime, concourse density spikes; recommend "
            "fans use upper-level amenities. Organizers may open secondary gates to relieve pressure."
        ),
    },
    {
        "id": "faq-lost-child",
        "title": "Lost child procedure",
        "text": (
            "Report a lost child immediately to any volunteer or first-aid station. The organizer "
            "team is notified and a targeted response is coordinated. Remain at your last known "
            "location if possible."
        ),
    },
    {
        "id": "faq-languages",
        "title": "Multilingual assistance",
        "text": (
            "The smart assistant responds in the fan's selected language and can translate any "
            "answer. Supported languages include English, Spanish, Portuguese, French, Arabic, "
            "Mandarin, Japanese, Korean, German, and Italian."
        ),
    },
]
