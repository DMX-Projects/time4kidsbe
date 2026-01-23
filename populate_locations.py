"""
Script to populate franchise locations with initial data.
Run this from Django shell: python manage.py shell < populate_locations.py
"""

from franchises.models import FranchiseLocation

# City data from CityLandmarks.tsx
locations_data = [
    {"name": "Alleppey", "landmark": "Alappuzha Backwaters", "type": "backwaters"},
    {"name": "Arcot", "landmark": "Arcot Nawab Fort", "type": "fort_generic"},
    {"name": "Barasat", "landmark": "Dakshineswar Kali Temple", "type": "temple_bengal"},
    {"name": "Belgaum", "landmark": "Belgaum Fort", "type": "fort_generic"},
    {"name": "Bengaluru", "landmark": "Vidhana Soudha", "type": "vidhana_soudha"},
    {"name": "Bhadohi", "landmark": "Carpet Weaving Hubs", "type": "carpet"},
    {"name": "Bhadrak", "landmark": "Akhandalamani Temple", "type": "temple_kalinga"},
    {"name": "Bhubaneswar", "landmark": "Lingaraja Temple", "type": "temple_kalinga"},
    {"name": "Ernakulam", "landmark": "Marine Drive Kochi", "type": "marine_drive"},
    {"name": "Hooghly", "landmark": "Bandel Church", "type": "bandel_church"},
    {"name": "Hosur", "landmark": "Chandira Choodeswarar Temple", "type": "temple_hill"},
    {"name": "Howrah", "landmark": "Howrah Bridge", "type": "howrah_bridge"},
    {"name": "Hyderabad", "landmark": "Charminar", "type": "charminar"},
    {"name": "Idukki", "landmark": "Idukki Arch Dam", "type": "arch_dam"},
    {"name": "Jamnagar", "landmark": "Lakhota Fort", "type": "fort_water"},
    {"name": "Kanchipuram", "landmark": "Kamakshi Amman Temple", "type": "temple_gopuram"},
    {"name": "Kollam", "landmark": "Ashtamudi Lake", "type": "backwaters"},
    {"name": "Kottayam", "landmark": "Vembanad Lake", "type": "lake_generic"},
    {"name": "Kozhikode", "landmark": "Kozhikode Beach", "type": "beach_generic"},
    {"name": "Lucknow", "landmark": "Bara Imambara", "type": "bara_imambara"},
    {"name": "Malappuram", "landmark": "Kottakkunnu Hills", "type": "hill_park"},
    {"name": "Mumbai", "landmark": "Gateway of India", "type": "gateway_of_india"},
    {"name": "Namakkal", "landmark": "Namakkal Rock Fort", "type": "rockfort"},
    {"name": "Nizamabad", "landmark": "Nizamabad Fort", "type": "fort_generic"},
    {"name": "Patna", "landmark": "Golghar", "type": "golghar"},
    {"name": "Pudukkottai", "landmark": "Thirumayam Fort", "type": "fort_generic"},
    {"name": "Pune", "landmark": "Shaniwar Wada", "type": "shaniwar_wada"},
    {"name": "Rajapalayam", "landmark": "Ayyanar Falls", "type": "waterfall"},
    {"name": "Ramanathapuram", "landmark": "Ramanathaswamy Temple", "type": "temple_gopuram"},
    {"name": "Rangareddy District", "landmark": "Ananthagiri Hills", "type": "hill_park"},
    {"name": "Ranipet District", "landmark": "Walajapet Fort", "type": "fort_generic"},
    {"name": "Ratlam", "landmark": "Cactus Garden", "type": "cactus_garden"},
    {"name": "Thiruninravur", "landmark": "Veera Raghava Perumal Temple", "type": "temple_gopuram"},
    {"name": "Thiruthangal", "landmark": "Karunellinathar Temple", "type": "temple_hill"},
    {"name": "Thrissur", "landmark": "Vadakkunnathan Temple", "type": "temple_kerala"},
    {"name": "Trichy", "landmark": "Rockfort Temple", "type": "rockfort"},
    {"name": "Trivandrum", "landmark": "Padmanabhaswamy Temple", "type": "temple_padmanabhaswamy"},
    {"name": "Vallioor", "landmark": "Sri Adikesava Perumal Temple", "type": "temple_gopuram"},
    {"name": "Vellore", "landmark": "Vellore Fort", "type": "fort_moat"},
    {"name": "Visakhapatnam", "landmark": "RK Beach", "type": "beach_rk"},
]

print("Starting to populate franchise locations...")
created_count = 0
skipped_count = 0

for idx, loc in enumerate(locations_data):
    city_name = loc["name"]
    landmark_name = loc["landmark"]
    landmark_type = loc["type"]
    
    # Check if already exists
    if FranchiseLocation.objects.filter(city_name=city_name).exists():
        print(f"✓ Skipping {city_name} (already exists)")
        skipped_count += 1
        continue
    
    # Create new location
    FranchiseLocation.objects.create(
        city_name=city_name,
        landmark_name=landmark_name,
        landmark_type=landmark_type,
        is_active=True,
        display_order=idx
    )
    print(f"✓ Created {city_name} - {landmark_name}")
    created_count += 1

print(f"\n✅ Population complete!")
print(f"   Created: {created_count} locations")
print(f"   Skipped: {skipped_count} locations (already existed)")
print(f"   Total: {len(locations_data)} locations")
