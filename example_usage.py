#!/usr / bin / env python3
# SPDX - License - Identifier: MIT
# Copyright (c) 2025 Perday CatalogLAB™

"""
Simple example demonstrating bulk - upsert - helpers usage.

Run with: python example_usage.py
Requires: pip install bulk - upsert - helpers[mysql]
"""

from bulk_upsert_helpers import bulk_upsert, get_or_create
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
)


def main():
    # Use SQLite for easy demo (no MySQL setup required)
    # Note: This example shows the API, but bulk_upsert requires MySQL for ON DUPLICATE KEY UPDATE
    engine = create_engine("sqlite:///demo.db", echo=True)

    metadata = MetaData()

    # Create example tables
    labels = Table(
        "labels",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100)),
        Column("country", String(2)),
        UniqueConstraint("name", "country", name="uq_label_country"),
    )

    tracks = Table(
        "tracks",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String(200)),
        Column("artist", String(100)),
        Column("label_id", Integer),
        Column("duration_ms", Integer),
    )

    # Create tables
    metadata.create_all(engine)

    print("🎵 Music Data Pipeline Example")
    print("=" * 40)

    # Step 1: Get - or - create reference data (labels)
    with engine.begin() as conn:
        print("\n📋 Creating reference data...")

        sony_id = get_or_create(
            conn, labels, name="Sony Music Entertainment", country="US"
        )
        warner_id = get_or_create(conn, labels, name="Warner Music Group", country="US")

        print(f"✅ Sony Music ID: {sony_id}")
        print(f"✅ Warner Music ID: {warner_id}")

    # Step 2: Bulk upsert track data
    print("\n🎶 Bulk upserting track data...")

    track_data = [
        {
            "title": "Blinding Lights",
            "artist": "The Weeknd",
            "label_id": sony_id,
            "duration_ms": 200040,
        },
        {
            "title": "Watermelon Sugar",
            "artist": "Harry Styles",
            "label_id": sony_id,
            "duration_ms": 174000,
        },
        {
            "title": "Levitating",
            "artist": "Dua Lipa",
            "label_id": warner_id,
            "duration_ms": 203000,
        },
        {
            "title": "Good 4 U",
            "artist": "Olivia Rodrigo",
            "label_id": sony_id,
            "duration_ms": 178000,
        },
    ]

    try:
        # Note: This will fail with SQLite since it doesn't support ON DUPLICATE KEY UPDATE
        # For real usage, use MySQL: mysql+pymysql://user:pass@host / db
        affected = bulk_upsert(engine, tracks, track_data)
        print(f"✅ Processed {affected} track records")
    except Exception as e:
        print(f"ℹ️  Expected error with SQLite: {e}")
        print("💡 For real usage, use MySQL with: mysql+pymysql://user:pass@host / db")

        # Fallback: insert manually for demo
        with engine.begin() as conn:
            for track in track_data:
                conn.execute(tracks.insert().values(**track))
        print("✅ Inserted tracks using fallback method")

    # Step 3: Show results
    print("\n📊 Final Results:")
    with engine.begin() as conn:
        label_count = conn.execute(labels.select().count()).scalar()
        track_count = conn.execute(tracks.select().count()).scalar()

        print(f"📋 Labels: {label_count}")
        print(f"🎶 Tracks: {track_count}")

        print("\n🎵 Track List:")
        results = conn.execute(tracks.select().order_by(tracks.c.title)).fetchall()
        for track in results:
            print(f"  • {track.title} by {track.artist} ({track.duration_ms}ms)")

    print("\n✨ Demo complete! Check demo.db for results.")


if __name__ == "__main__":
    main()
