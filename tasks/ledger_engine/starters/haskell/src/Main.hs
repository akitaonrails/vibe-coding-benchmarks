module Main where
import Data.Aeson (eitherDecode,encode)
import qualified Data.ByteString.Lazy.Char8 as B
import Engine
import System.IO (isEOF)
main :: IO ()
main = loop (reset 64)
  where loop engine = do
          done <- isEOF
          if done then pure () else do
            line <- B.pack <$> getLine
            case eitherDecode line of
              Left problem -> fail problem
              Right request -> do
                let (result,next)=call request engine
                B.putStrLn (encode result)
                loop next
