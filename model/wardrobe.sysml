package WardrobeSystem {
    doc /* Small teaching model: a wardrobe that stores garments.
          Covers structure (parts), requirements, and behaviour (the "store garment" process). */

    import ScalarValues::*;

    // ------------------------------------------------------------------
    // 1. Types
    // ------------------------------------------------------------------
    enum def CleanState {
        enum clean;
        enum dirty;
    }

    // ------------------------------------------------------------------
    // 2. Requirements
    // ------------------------------------------------------------------
    requirement def <'R1'> SufficientSpace {
        doc /* The wardrobe shall have enough free volume for the garment being stored. */
        attribute freeVolume : Real;
        attribute garmentVolume : Real;
        require constraint { freeVolume >= garmentVolume }
    }

    requirement def <'R2'> CleanGarmentOnly {
        doc /* Only clean garments shall be stored in the wardrobe. */
        attribute garmentState : CleanState;
        require constraint { garmentState == CleanState::clean }
    }

    // ------------------------------------------------------------------
    // 3. Structure
    // ------------------------------------------------------------------
    part def Garment {
        doc /* A piece of clothing with its own storage-relevant properties. */
        attribute name : String;
        attribute volume : Real;
        attribute state : CleanState;

        requirement mustBeClean : CleanGarmentOnly {
            attribute :>> garmentState = state;
        }
    }

    part def Wardrobe {
        doc /* Main part of the system. Holds a variable number of garments. */
        attribute capacity : Real;
        attribute usedVolume : Real;
        attribute freeVolume : Real = capacity - usedVolume;

        part garments : Garment[0..*];

        requirement hasSpace : SufficientSpace {
            attribute :>> freeVolume = capacity - usedVolume;
        }
    }

    // ------------------------------------------------------------------
    // 4. Behaviour: the "store garment" process
    // ------------------------------------------------------------------
    action def StoreGarment {
        doc /* Store one garment in the wardrobe.
              Preconditions are the two requirements above: the garment is clean (R2)
              and the wardrobe has free space (R1). */

        in item garment : Garment;
        in item wardrobe : Wardrobe;

        action checkClean;   // verifies R2
        action checkSpace;   // verifies R1
        action place;        // adds the garment to the wardrobe and updates usedVolume

        first start;
        then checkClean;
        then checkSpace;
        then place;
        then done;
    }

    // ------------------------------------------------------------------
    // 5. Example configuration
    // ------------------------------------------------------------------
    part myWardrobe : Wardrobe {
        attribute :>> capacity = 100.0;
        attribute :>> usedVolume = 40.0;

        part tShirt : Garment :> garments {
            attribute :>> name = "white t-shirt";
            attribute :>> volume = 2.0;
            attribute :>> state = CleanState::clean;
        }
        part jeans : Garment :> garments {
            attribute :>> name = "blue jeans";
            attribute :>> volume = 5.0;
            attribute :>> state = CleanState::dirty;
        }
    }

    // One run of the process, for the t-shirt (inputs would be bound to myWardrobe::tShirt and myWardrobe).
    action storeTShirt : StoreGarment;

    // ------------------------------------------------------------------
    // 6. Traceability: which part satisfies which requirement
    // ------------------------------------------------------------------
    requirement spaceReq : SufficientSpace;
    requirement cleanReq : CleanGarmentOnly;

    satisfy spaceReq by myWardrobe;
    satisfy cleanReq by myWardrobe::tShirt;
}
