{-# LANGUAGE OverloadedStrings #-}
module Device where
import Domain
import Data.Aeson hiding (Key)
import Data.Text (Text)
import qualified Data.Map.Strict as M
import Data.List (foldl')

data Device = Device { capacity :: Int, image :: Value, journal :: [Frame], legacyOwner :: Maybe Text, loaded :: Bool } deriving Show
emptyDevice :: Int -> Device
emptyDevice c = Device c (obj [("schema",int 2),("revision",int 0),("entries",arr []),("receipts",arr [])]) [] Nothing False
append :: [Frame] -> Maybe Value -> Device -> Device
append fs _ device = device { journal=journal device++fs }
publish :: Value -> Maybe Value -> Device -> Device
publish next _ device = device { image=next,journal=[],legacyOwner=Nothing }
loadImage :: Value -> Text -> Device -> Device
loadImage next tenant device = device {image=next,legacyOwner=Just tenant,loaded=True,journal=[]}
groups :: [Frame] -> [(Frame,[Frame])]
groups (header@(BeginFrame _ _ revision count):rest) =
  let (edits,tailFrames)=splitAt count rest
      isEdit (EditFrame _ _) = True
      isEdit _ = False
  in case tailFrames of
    SealFrame sealed:remaining | length edits==count && all isEdit edits && sealed==revision -> (header,edits):groups remaining
    _ -> []
groups _=[]
recover :: Device -> (Table,Receipts,Int,Device)
recover device = (table,receipts,revision,device {journal=take consumed (journal device)})
  where stored=image device
        tenant e=if number "schema" stored==1 then legacyOwner device `orElse` "legacy" else text "tenant" e
        convert e=let r=field "row" e in if r==Null then Nothing else Just (record (tenant e) (text "id" e) r)
        initialTable=M.fromList [(Key (tenant e) (text "id" e),Entry (number "version" e) (convert e))|e<-items (field "entries" stored)]
        initialReceipts=M.fromList [(Key (tenant r) (text "request" r),number "revision" r)|r<-items (field "receipts" stored)]
        complete=groups (journal device)
        consumed=sum [length edits+2|(_,edits)<-complete]
        apply (t,rs,_) (BeginFrame own request rev _,edits)=
          (foldl' (\acc edit->case edit of EditFrame ident r->M.insert (Key own ident) (Entry rev r) acc; _->acc) t edits,M.insert (Key own request) rev rs,rev)
        apply state _=state
        (table,receipts,revision)=foldl' apply (initialTable,initialReceipts,number "revision" stored) complete
inspect :: Text -> Device -> Value
inspect tenant device = obj [("checkpoint",filtered),("journal",arr fs)]
  where stored=image device
        permitted e=if number "schema" stored==1 then legacyOwner device==Just tenant else text "tenant" e==tenant
        filtered=foldr (\k im->set k (arr (filter permitted (items (field k stored)))) im) stored ["entries","receipts"]
        fs=map frameJSON (concat [h:edits++[SealFrame rev] | (h@(BeginFrame own _ rev _),edits)<-groups (journal device),own==tenant])
