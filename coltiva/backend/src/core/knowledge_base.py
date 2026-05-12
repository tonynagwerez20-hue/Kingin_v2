"""
COLTIVA KNOWLEDGE BASE
Hardcoded crop recommendation data for AERIS Group's Coltiva platform.

Data source: AERIS Crop Intelligence Database v2.1 (Lango Sub-Region, Uganda)
Crops: maize, sesame, sunflower, sorghum, soybeans, cassava

Usage:
    from core.knowledge_base import get_crop_summary, get_topic_for_crop
    
    summary = get_crop_summary("maize")
    planting_info = get_topic_for_crop("maize", "planting")
"""

from typing import Dict, List, Any, Optional

# =============================================================================
# DESIGN RULES - Coltiva's 8 Fundamental Rules
# =============================================================================

DESIGN_RULES = {
    "rule_1": "NEVER use kg/ha — use bottle caps, bags/acre, or UGX only",
    "rule_2": "DEFAULT to MICRO-DOSE for farmers under 2 acres",
    "rule_3": "Show net income gain (Spend UGX X → Earn UGX Y extra)",
    "rule_4": "For SOYBEANS: lead with Rhizobium inoculant",
    "rule_5": "For CASSAVA: certified CMD-resistant cuttings first",
    "rule_6": "For SUNFLOWER: ALWAYS include borax",
    "rule_7": "Link to LinkTrade prices when possible",
    "rule_8": "Keep responses under 250 characters"
}

# Bottle cap measurement: 1 cap = 8-10g of granular fertiliser
BOTTLE_CAP_GRAMS = 8  # Average grams per bottle cap

# =============================================================================
# KNOWLEDGE BASE - Crop Data
# =============================================================================

KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "maize": {
        "planting": {
            "advice": "Plant at onset of rains. In Lango region, optimal planting is March-April for first season and August-September for second season.",
            "varieties": ["SC627", "SC628", "Longe 10", "Longe 8", "KH500-14A"],
            "soil": "Well-drained loamy soils with pH 5.5-7.0. Avoid heavy clay or waterlogged areas.",
            "seed_rate": "25 kg/acre (approximately 2 bags of 12.5kg each)",
            "depth": "2.5-5 cm (1-2 inches) deep",
            "spacing": "75cm between rows, 25-30cm between plants",
            "season": "First season: March-April; Second season: August-September"
        },
        "fertiliser": {
            "default_method": "micro-dose",
            "method": " Apply 1 bottle cap (8g) of DAP per hole at planting. Top-dress with 1 bottle cap Urea at 6 weeks after planting.",
            "cost_per_acre": "UGX 180,000-220,000",
            "cost_details": "DAP 2x50kg bags @ UGX 155,000 = UGX 310,000 OR 25 bottle caps = UGX 50,000; Urea 1x50kg = UGX 95,000",
            "yield_increase": "100-150% yield increase compared to no fertilizer",
            "roi_message": "Spend UGX 180,000 → Earn UGX 800,000-1,200,000 extra (4-6x return)",
            "warning": "Do not apply DAP and Urea together - burn seeds. Apply DAP in hole, Urea 6 weeks later."
        },
        "pest": {
            "stem_borer": {
                "symptoms": "Dead heart in young plants, borers inside stem, frass (powder) at entry holes",
                "threshold": "50% of plants showing damage",
                "treatment": "Use Cypermethrin 5EC @ 10ml/20L water. Spray at 2 and 6 weeks after planting.",
                "prevention": "Early planting, remove crop residues, intercrop with legumes"
            },
            "aphids": {
                "symptoms": "Curled leaves, sticky honeydew, ants on plants",
                "threshold": "Any visible infestation",
                "treatment": "Oxydemeton methyl @ 10ml/20L water",
                "prevention": "Intercrop with onions, marigold"
            },
            "maize_weevil": {
                "symptoms": " holes in stored grain, flour-like powder",
                "threshold": "Any detection in storage",
                "treatment": "Actellic dust 2%, mix 50g per 100kg grain",
                "prevention": "Dry grain to 13% moisture, use hermetic storage"
            }
        },
        "disease": {
            "maize_lethal_necrosis": {
                "symptoms": "Yellow streaks, severe stunting, dead tassels",
                "control": "No chemical control. Use resistant varieties (SC627, Longe 10).",
                "prevention": "Plant early, control thrips, use certified seed"
            },
            "rust": {
                "symptoms": "Orange-brown pustules on leaves",
                "control": "Mancozeb @ 50g/20L water as preventive",
                "prevention": "Use resistant varieties, avoid overhead irrigation"
            },
            "blight": {
                "symptoms": "Large lesions with gray centers on leaves",
                "control": "Azoxystrobin @ 20ml/20L water",
                "prevention": "Crop rotation, remove infected debris"
            }
        },
        "harvest": {
            "timing": "90-120 days after planting (depending on variety). Harvest when cobs turn brown and leaves dry.",
            "moisture": "Dry to 13-14% moisture before storage",
            "storage": "Store on raised platforms, in cribs, or airtight containers. Check monthly for pests.",
            "yield_potential": "3,000-5,000 kg/acre (30-50 bags of 100kg)",
            "yield_message": "With micro-dose fertilizer: 3,000-5,000 kg/acre. Without: 1,500-2,000 kg/acre."
        },
        "varieties": {
            "SC627": { "maturity": "90-100 days", "yield": "4,000-5,000 kg/acre", "traits": "Drought tolerant, MLN resistant", "seed_source": "Seed Co" },
            "SC628": { "maturity": "95-110 days", "yield": "4,500-5,500 kg/acre", "traits": "High yielding, MLN resistant", "seed_source": "Seed Co" },
            "Longe 10": { "maturity": "100-120 days", "yield": "4,000-5,200 kg/acre", "traits": "Drought tolerant, QPM", "seed_source": "NARO" },
            "Longe 8": { "maturity": "90-100 days", "yield": "3,500-4,500 kg/acre", "traits": "Early maturity", "seed_source": "NARO" },
            "KH500-14A": { "maturity": "95-105 days", "yield": "3,800-4,800 kg/acre", "traits": "Good for mid-altitude", "seed_source": "KARI" }
        }
    },
    "sesame": {
        "planting": {
            "advice": "Sow directly after land preparation. In Lango, plant April-May for first season and August-September for second season.",
            "varieties": ["Serudo", "NABANET", "Local White", "Pong Pong"],
            "soil": "Well-drained sandy loam, pH 5.5-7.0. Avoid heavy clay.",
            "seed_rate": "4-5 kg/acre (approximately 6,000-8,000 plants)",
            "depth": "1-2 cm (0.5-1 inch)",
            "spacing": "45cm between rows, 15-20cm between plants",
            "season": "First season: April-May; Second season: August-September"
        },
        "fertiliser": {
            "default_method": "micro-dose",
            "method": "Apply 1 bottle cap (8g) DAP per hole at planting. Sesame is drought-tolerant - avoid excess N.",
            "cost_per_acre": "UGX 80,000-120,000",
            "cost_details": "DAP 1x50kg bag = UGX 155,000; apply at 10 bottle caps/acre = UGX 31,000",
            "yield_increase": "50-80% yield increase",
            "roi_message": "Spend UGX 80,000 → Earn UGX 300,000-500,000 extra (3-4x return)",
            "warning": "Too much nitrogen causes excessive leaf growth and reduces seed set."
        },
        "pest": {
            "sesame_gall_midge": {
                "symptoms": "Swollen stems, gall formation, stunt growth",
                "threshold": "10% of plants affected",
                "treatment": "No effective chemical control. Remove and burn affected plants.",
                "prevention": "Crop rotation, use clean seed"
            },
            "aphids": {
                "symptoms": "Leaves curl, sticky honeydew",
                "threshold": "Any heavy infestation",
                "treatment": "Carbofuran granules applied at planting",
                "prevention": "Intercrop with maize"
            },
            "leafhoppers": {
                "symptoms": "Yellowing, stunted growth, leaf curl",
                "threshold": "5-10 per plant",
                "treatment": "Imidacloprid @ 5ml/20L water",
                "prevention": "Remove wild sesame hosts"
            }
        },
        "disease": {
            "phytophthora_blight": {
                "symptoms": "Water-soaked lesions, stem rot, plant death",
                "control": "Metalaxyl + Mancozeb @ 50g/20L",
                "prevention": "Well-drained soil, crop rotation"
            },
            "fusarium_wilt": {
                "symptoms": "Yellowing, wilting, brown vascular tissue",
                "control": "No control. Remove affected plants.",
                "prevention": "Resistant varieties, crop rotation"
            },
            "cercospora_leaf_spot": {
                "symptoms": "Brown spots with gray centers on leaves",
                "control": "Mancozeb @ 50g/20L water",
                "prevention": "Remove crop residues"
            }
        },
        "harvest": {
            "timing": "80-100 days after planting. Harvest when lower leaves drop and capsules turn yellow-brown.",
            "moisture": "Dry to 8-10% moisture",
            "storage": "Store in tight containers or bags in cool, dry place. Avoid moisture absorption.",
            "yield_potential": "400-800 kg/acre (4-8 bags of 100kg)",
            "yield_message": "With micro-dose: 500-800 kg/acre. Without: 200-400 kg/acre."
        },
        "varieties": {
            "Serudo": { "maturity": "80-90 days", "yield": "500-700 kg/acre", "traits": "High oil content", "seed_source": "NARO" },
            "NABANET": { "maturity": "85-95 days", "yield": "600-800 kg/acre", "traits": "Shatter-resistant", "seed_source": "NARO" },
            "Local White": { "maturity": "90-100 days", "yield": "400-600 kg/acre", "traits": "Adapted locally", "seed_source": "Local markets" },
            "Pong Pong": { "maturity": "85-95 days", "yield": "500-700 kg/acre", "traits": "Early maturing", "seed_source": "Local markets" }
        }
    },
    "sunflower": {
        "planting": {
            "advice": "Plant at onset of rains or anytime during rainy season. Full sun required.",
            "varieties": ["Sungold 6001", "Panado", "White Stallion", "Red Stallion"],
            "soil": "Well-drained fertile soils, pH 5.5-7.5. Tolerates poor soils.",
            "seed_rate": "5-8 kg/acre",
            "depth": "2.5-5 cm (1-2 inches)",
            "spacing": "60cm between rows, 25cm between plants",
            "season": "March-September (first season preferred)"
        },
        "fertiliser": {
            "default_method": "micro-dose-with-borax",
            "method": "Apply 1 bottle cap (8g) DAP per hole at planting + BORAX 5g per hole for bor deficiency. Boron is ESSENTIAL for sunflower.",
            "cost_per_acre": "UGX 150,000-200,000",
            "cost_details": "DAP 1x50kg = UGX 155,000; Borax 5kg = UGX 80,000",
            "yield_increase": "30-50% yield increase with borax",
            "roi_message": "Spend UGX 200,000 → Earn UGX 400,000-600,000 extra (2-3x return)",
            "warning": "BORON DEFICIENCY causes hollow heads and poor seed fill. ALWAYS add borax for sunflower!"
        },
        "pest": {
            "birds": {
                "symptoms": "Seeds eaten from heads before harvest",
                "threshold": "Any bird activity",
                "treatment": "Scare tactics, bird netting",
                "prevention": "Harvest early, use bird-resistant varieties"
            },
            "aphids": {
                "symptoms": "Stunted growth, yellow leaves",
                "threshold": "Heavy infestation",
                "treatment": "Imidacloprid @ 5ml/20L water",
                "prevention": "Intercrop with legumes"
            },
            "stem_weevil": {
                "symptoms": "Holes in stem, wilting",
                "threshold": "10% damage",
                "treatment": "Cypermethrin @ 10ml/20L water",
                "prevention": "Crop rotation"
            }
        },
        "disease": {
            "downy_mildew": {
                "symptoms": "Yellow leaves, white growth on undersides",
                "control": "Metalaxyl as seed treatment",
                "prevention": "Use treated seed"
            },
            "rust": {
                "symptoms": "Orange-brown pustules",
                "control": "Mancozeb @ 50g/20L water",
                "prevention": "Remove infected debris"
            },
            "sclerotinia_stalk_rot": {
                "symptoms": "White mold, soft stems",
                "control": "No effective chemical control",
                "prevention": "Crop rotation with cereals"
            }
        },
        "harvest": {
            "timing": "80-100 days. Harvest when back of head turns brown and seeds loosen easily.",
            "moisture": "Dry to 9-10% moisture",
            "storage": "Store in dry, ventilated area. Protect from birds and rodents.",
            "yield_potential": "800-1,500 kg/acre (8-15 bags)",
            "yield_message": "With micro-dose + borax: 1,000-1,500 kg/acre. Without: 600-800 kg/acre."
        },
        "varieties": {
            "Sungold 6001": { "maturity": "85-95 days", "yield": "1,200-1,500 kg/acre", "traits": "High yielding, oil type", "seed_source": "Seed Co" },
            "Panado": { "maturity": "90-100 days", "yield": "1,000-1,300 kg/acre", "traits": "Medium height", "seed_source": "Local markets" },
            "White Stallion": { "maturity": "95-110 days", "yield": "1,000-1,200 kg/acre", "traits": "White seeds", "seed_source": "Pannar" },
            "Red Stallion": { "maturity": "95-110 days", "yield": "1,000-1,200 kg/acre", "traits": "Red seeds", "seed_source": "Pannar" }
        }
    },
    "sorghum": {
        "planting": {
            "advice": "Plant at onset of rains. Sorghum is drought-tolerant - can be planted later than other crops.",
            "varieties": ["NAROSorghum-1", "NAROSorghum-2", "Sekedo", "Seso 14"],
            "soil": "Wide adaptation, tolerates poor and saline soils. pH 5.5-8.0.",
            "seed_rate": "8-10 kg/acre",
            "depth": "2.5-5 cm (1-2 inches)",
            "spacing": "60-75cm between rows, 20-25cm between plants",
            "season": "March-May preferred, can plant to August"
        },
        "fertiliser": {
            "default_method": "micro-dose",
            "method": "Apply 1 bottle cap (8g) DAP per hole at planting. Sorghum is drought-tolerant - moderate fertilizer only.",
            "cost_per_acre": "UGX 80,000-120,000",
            "cost_details": "DAP 1x50kg = UGX 155,000; 10 caps = UGX 31,000",
            "yield_increase": "30-50% yield increase",
            "roi_message": "Spend UGX 80,000 → Earn UGX 200,000-400,000 extra (2-3x return)",
            "warning": "Excess fertilizer causes lodging and delays maturity in drought conditions."
        },
        "pest": {
            "sorghum_midge": {
                "symptoms": "Empty grains, pink larvae in head",
                "threshold": "1 adult per 10 heads at flowering",
                "treatment": "Carbaryl @ 40g/20L water at flowering",
                "prevention": "Early planting, tolerant varieties"
            },
            "stem_borer": {
                "symptoms": "Dead heart, borers in stem",
                "threshold": "30% damage",
                "treatment": "Cypermethrin @ 10ml/20L water",
                "prevention": "Remove crop residues"
            },
            "aphids": {
                "symptoms": "Yellow leaves, sticky honeydew",
                "threshold": "Heavy infestation",
                "treatment": "Oxydemeton methyl @ 10ml/20L",
                "prevention": "Intercrop with legumes"
            }
        },
        "disease": {
            "anthracnose": {
                "symptoms": "Red-brown lesions on leaves",
                "control": "Mancozeb @ 50g/20L water",
                "prevention": "Resistant varieties, crop rotation"
            },
            "grain_mold": {
                "symptoms": "Moldy grains, pink growth",
                "control": "Timely harvest, proper drying",
                "prevention": "Early planting, harvest early"
            },
            "striga": {
                "symptoms": "Purple flowers, parasitic on roots",
                "control": "Hand pulling, rotation with legumes",
                "prevention": "IMUSTARD trap crop"
            }
        },
        "harvest": {
            "timing": "90-120 days. Harvest when grains are hard and heads turn brown.",
            "moistity": "Dry to 12-13% moisture",
            "storage": "Store in dry place, protect from pests. Traditional storage in granaries.",
            "yield_potential": "2,000-4,000 kg/acre (20-40 bags)",
            "yield_message": "With micro-dose: 2,500-4,000 kg/acre. Without: 1,500-2,500 kg/acre."
        },
        "varieties": {
            "NAROSorghum-1": { "maturity": "90-100 days", "yield": "2,500-3,500 kg/acre", "traits": "Drought tolerant", "seed_source": "NARO" },
            "NAROSorghum-2": { "maturity": "100-120 days", "yield": "3,000-4,000 kg/acre", "traits": "High yielding", "seed_source": "NARO" },
            "Sekedo": { "maturity": "90-110 days", "yield": "2,000-3,000 kg/acre", "traits": "Early maturing", "seed_source": "Local markets" },
            "Seso 14": { "maturity": "95-110 days", "yield": "2,500-3,500 kg/acre", "traits": "Good for brewing", "seed_source": "NARO" }
        }
    },
    "soybeans": {
        "planting": {
            "advice": "Plant at onset of rains. Inoculation with Rhizobium is CRITICAL for nitrogen fixation.",
            "varieties": ["Soybeans 1 (SB1)", "SB2", "SB3", "MakSoy 3N", "Namsoy 4M"],
            "soil": "Well-drained fertile loam, pH 5.5-7.0. Avoid waterlogged soils.",
            "seed_rate": "80-100 kg/acre (80-100 kg for dense planting)",
            "depth": "2.5-5 cm (1-2 inches)",
            "spacing": "45-60cm between rows, 5-10cm between plants",
            "season": "March-May (first season), August-September (second season)"
        },
        "fertiliser": {
            "default_method": "inoculant-first",
            "method": "1. Mix 10g Rhizobium inoculant per 8kg seed BEFORE planting. 2. Apply 1 bottle cap (8g) DAP per hole at planting. Inoculant provides N - minimal fertilizer needed.",
            "cost_per_acre": "UGX 100,000-150,000",
            "cost_details": "Rhizobium inoculant 100g = UGX 30,000; DAP 1x50kg = UGX 155,000 (10 caps only needed)",
            "yield_increase": "40-80% with Rhizobium",
            "roi_message": "Spend UGX 100,000 → Earn UGX 400,000-800,000 extra Rhizobium gives FREE nitrogen!",
            "warning": "Rhizobium MUST be applied to seeds BEFORE planting. Cannot be mixed with fertilizer in soil."
        },
        "pest": {
            "aphids": {
                "symptoms": "Curled leaves, yellowing, sticky honeydew",
                "threshold": "Any heavy infestation",
                "treatment": "Imidacloprid @ 5ml/20L water",
                "prevention": "Intercrop with maize"
            },
            "stink_bugs": {
                "symptoms": "Damaged seeds, shriveled pods",
                "threshold": "10 bugs per 10 plants",
                "treatment": "Cypermethrin @ 10ml/20L water",
                "prevention": "Early planting"
            },
            "pod_borers": {
                "symptoms": "Holes in pods, seed damage",
                "threshold": "20% pod damage",
                "treatment": "Carbaryl @ 40g/20L water",
                "prevention": "Crop rotation"
            }
        },
        "disease": {
            "rust": {
                "symptoms": "Brown pustules, leaf drop",
                "control": "Triadimefon @ 10g/20L water",
                "prevention": "Early planting, resistant varieties"
            },
            "bacterial_blight": {
                "symptoms": "Brown lesions with yellow halos",
                "control": "Copper oxychloride @ 50g/20L",
                "prevention": "Clean seed, crop rotation"
            },
            "soybean_mosaic": {
                "symptoms": "Mottled leaves, stunted plants",
                "control": "No control. Use certified clean seed.",
                "prevention": "Control aphids, use clean seed"
            }
        },
        "harvest": {
            "timing": "70-90 days. Harvest when leaves turn yellow and pods are brown and dry.",
            "moisture": "Dry to 12-13% moisture",
            "storage": "Store in dry place. Soybeans should be stored at 12% moisture or below.",
            "yield_potential": "1,500-2,500 kg/acre (15-25 bags)",
            "yield_message": "With Rhizobium: 1,800-2,500 kg/acre. Without: 1,000-1,500 kg/acre."
        },
        "varieties": {
            "Soybeans 1 (SB1)": { "maturity": "70-80 days", "yield": "1,500-2,000 kg/acre", "traits": "Early maturing", "seed_source": "NARO" },
            "SB2": { "maturity": "75-85 days", "yield": "1,800-2,200 kg/acre", "traits": "Medium maturity", "seed_source": "NARO" },
            "SB3": { "maturity": "80-90 days", "yield": "2,000-2,500 kg/acre", "traits": "High yielding", "seed_source": "NARO" },
            "MakSoy 3N": { "maturity": "75-85 days", "yield": "1,800-2,300 kg/acre", "traits": "N-deficient tolerant", "seed_source": "Makerere" },
            "Namsoy 4M": { "maturity": "80-90 days", "yield": "2,000-2,500 kg/acre", "traits": "Large seed", "seed_source": "NARO" }
        }
    },
    "cassava": {
        "planting": {
            "advice": "Plant stems (cuttings) horizontally or at 45° angle. In Lango, plant March-April or August-September.",
            "varieties": ["NAROCass 1", "NAROCass 2", "Mwendano", "Bamunanik", "CRAN 001 (TME14)"],
            "soil": "Well-drained sandy loam, pH 5.5-7.0. Tolerates poor soils.",
            "seed_rate": "100 stems/acre (25-30cm long cuttings)",
            "depth": "10-15cm deep (horizontal) or 20-25cm (vertical)",
            "spacing": "1m x 1m (10,000 plants/acre) or 1m x 0.8m (12,500 plants/acre)",
            "season": "March-September (warm soils)"
        },
        "fertiliser": {
            "default_method": "organic-first",
            "method": "Apply well-rotten manure 2-3 tons/acre before planting. After 3 months, apply 1 bottle cap (8g) NPK per plant if soils are poor.",
            "cost_per_acre": "UGX 100,000-200,000 for manure transport",
            "cost_details": "Manure 3 tons = UGX 150,000-300,000; NPK 1x50kg = UGX 95,000 (use sparingly)",
            "yield_increase": "30-50% with manure",
            "roi_message": "Spend UGX 200,000 on manure → Earn UGX 500,000-1,000,000 extra (2-5x return)",
            "warning": "Cassava is tolerant of poor soils. Excessive fertilizer wastes money."
        },
        "pest": {
            "cassava_mealybug": {
                "symptoms": "Stunted tips, sooty mold, leaf dropping",
                "threshold": "Any severe infestation",
                "treatment": "Imidacloprid @ 5ml/20L water",
                "prevention": "Use clean planting material"
            },
            "green_mite": {
                "symptoms": "Yellowing, leaf drop, stunted growth",
                "threshold": "10 mites per leaf",
                "treatment": "No effective chemical - use resistant varieties",
                "prevention": "Plant resistant varieties"
            },
            " termites": {
                "symptoms": "Cut stems, wilting plants",
                "threshold": "Any activity",
                "treatment": "Fipronil @ 5ml/20L water around plants",
                "prevention": "Avoid dry season planting"
            }
        },
        "disease": {
            "cassava_mosaic_disease": {
                "symptoms": "Mottled leaves, stunted plants",
                "control": "NO CHEMICAL CONTROL. Use resistant varieties (CRAN 001/TME14, Mwendano).",
                "prevention": "Use CERTIFIED CMD-RESISTANT cuttings. This is the #1 rule for cassava!"
            },
            "cassava_bacterial_blight": {
                "symptoms": "Water-soaked lesions, leaf drop",
                "control": "Copper oxychloride @ 50g/20L",
                "prevention": "Use clean cuttings, rotation"
            },
            "root_rot": {
                "symptoms": "Soft, rotting roots",
                "control": "None - plant loss",
                "prevention": "Well-drained soil, avoid overwatering"
            }
        },
        "harvest": {
            "timing": "8-18 months depending on variety. Harvest when leaves start yellowing and falling.",
            "moisture": "Process within 24-48 hours of harvest. Peel and slice for drying.",
            "storage": "PROCESS IMMEDIATELY - cannot store fresh roots. Dry chips for storage.",
            "yield_potential": "8,000-25,000 kg/acre (80-250 bags)",
            "yield_message": "With manure + good variety: 15,000-25,000 kg/acre. Without: 8,000-12,000 kg/acre."
        },
        "varieties": {
            "NAROCass 1": { "maturity": "12-18 months", "yield": "15,000-20,000 kg/acre", "traits": "High starch", "seed_source": "NARO" },
            "NAROCass 2": { "maturity": "12-15 months", "yield": "12,000-18,000 kg/acre", "traits": "Early maturing", "seed_source": "NARO" },
            "Mwendano": { "maturity": "12-18 months", "yield": "15,000-22,000 kg/acre", "traits": "CMD resistant", "seed_source": "Local" },
            "Bamunanik": { "maturity": "12-18 months", "yield": "12,000-18,000 kg/acre", "traits": "Drought tolerant", "seed_source": "Local" },
            "CRAN 001 (TME14)": { "maturity": "12-18 months", "yield": "18,000-25,000 kg/acre", "traits": "CMD RESISTANT - get this one!", "seed_source": "IITA" }
        }
    }
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_crop_names() -> List[str]:
    """Return list of all available crop names."""
    return list(KNOWLEDGE_BASE.keys())


def get_crop_descriptions() -> Dict[str, str]:
    """Return display names for crops."""
    return {
        "maize": "Maize (Corn)",
        "sesame": "Sesame (Simsim)",
        "sunflower": "Sunflower",
        "sorghum": "Sorghum",
        "soybeans": "Soybeans",
        "cassava": "Cassava"
    }


def get_crop_summary(crop: str) -> Dict[str, Any]:
    """Get summary information for a crop."""
    if crop not in KNOWLEDGE_BASE:
        return {}
    
    kb = KNOWLEDGE_BASE[crop]
    planting = kb.get("planting", {})
    fertiliser = kb.get("fertiliser", {})
    harvest = kb.get("harvest", {})
    
    return {
        "name": crop,
        "display_name": get_crop_descriptions().get(crop, crop),
        "planting_season": planting.get("season", "N/A"),
        "yield_potential": harvest.get("yield_potential", "N/A"),
        "micro_dose_cost": fertiliser.get("cost_per_acre", "N/A"),
        "yield_increase": fertiliser.get("yield_increase", "N/A"),
        "fertiliser_method": fertiliser.get("method", ""),
        "varieties_count": len(kb.get("varieties", {}))
    }


def get_topic_for_crop(crop: str, topic: str) -> Dict[str, Any]:
    """Get specific topic data for a crop.
    
    Args:
        crop: One of maize, sesame, sunflower, sorghum, soybeans, cassava
        topic: One of planting, fertiliser, pest, disease, harvest, varieties
    
    Returns:
        Dictionary with topic data, or empty dict if crop/topic not found
    """
    if crop not in KNOWLEDGE_BASE:
        return {}
    
    kb = KNOWLEDGE_BASE[crop]
    return kb.get(topic, {})


def get_micro_dose_info(crop: str) -> Dict[str, Any]:
    """Get micro-dose fertiliser information for a crop."""
    if crop not in KNOWLEDGE_BASE:
        return {}
    
    fertiliser = KNOWLEDGE_BASE[crop].get("fertiliser", {})
    return {
        "method": fertiliser.get("method", ""),
        "cost_per_acre": fertiliser.get("cost_per_acre", ""),
        "yield_increase": fertiliser.get("yield_increase", ""),
        "roi_message": fertiliser.get("roi_message", ""),
        "warning": fertiliser.get("warning", "")
    }


def compare_crops(crop1: str, crop2: str) -> Dict[str, Any]:
    """Compare two crops side by side."""
    summary1 = get_crop_summary(crop1)
    summary2 = get_crop_summary(crop2)
    
    return {
        "crop1": summary1,
        "crop2": summary2
    }


def get_design_rules() -> Dict[str, str]:
    """Return Coltiva's design rules."""
    return DESIGN_RULES.copy()