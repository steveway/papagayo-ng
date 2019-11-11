import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.List;


public class SiEnTransliteration {

	/**
	 * @param args
	 * @throws IOException 
	 */
	public static void main(String[] args) throws IOException {
		// TODO Auto-generated method stub
		
		String fileName = args[0];
		
		// ----------------- Get Unique words -----------------------------
		
		GetUniqueWords guw = new GetUniqueWords();
		List<String> uniqueWords = new ArrayList<String>();
		
		uniqueWords = guw.getUniqueWords(fileName);
		
		String names[] = fileName.split("\\.");
		String name = names[0];
		String unique_name = name.concat("_UniqueWords.txt");
		
		FileOutputStream uniqueFileOutputStream = new FileOutputStream(new File(unique_name));
	    BufferedWriter uniqueBufferedWriter = new BufferedWriter(new OutputStreamWriter(uniqueFileOutputStream, "UTF8"));
		
		for(String str : uniqueWords){
			uniqueBufferedWriter.write(str);
			uniqueBufferedWriter.write("\n");
		}
		
		uniqueBufferedWriter.close();
		
		// ------------------------------------------------------------------
		
		// --------------------Encode unique words --------------------------
		
		Transliterator localTransliterator = new Transliterator();
		String encode_name = name.concat("_EncodeWords.txt");
		
		FileInputStream encodeFileInputStream = new FileInputStream(new File(unique_name));
	    BufferedReader encodeBufferedReader = new BufferedReader(new InputStreamReader(encodeFileInputStream, "UTF8"));
	      
	    FileOutputStream encodeFileOutputStream = new FileOutputStream(new File(encode_name));
	    BufferedWriter encodeBufferedWriter = new BufferedWriter(new OutputStreamWriter(encodeFileOutputStream, "UTF8"));
	      
	    localTransliterator.encoder(encodeBufferedReader, encodeBufferedWriter);
	    encodeBufferedWriter.close();
	    
	    // ------------------------------------------------------------------
	    
	    // -------------------Translit unique words -------------------------
	    
	    Schwa_Analysis sa = new Schwa_Analysis();
		Hashtable<String, String> charType = sa.char_type();
		String translit_name = name.concat("_TranslitWords.txt");
		List<String> translitWords = new ArrayList<String>();
				
		FileInputStream translitFileInputStream = new FileInputStream(new File(encode_name));
		BufferedReader translitBufferedReader = new BufferedReader(new InputStreamReader(translitFileInputStream));
		
		FileOutputStream translitFileOutputStream = new FileOutputStream(new File(translit_name));
	    BufferedWriter translitBufferedWriter = new BufferedWriter(new OutputStreamWriter(translitFileOutputStream));
	      
	
		String line = translitBufferedReader.readLine();
		while(line != null){
			String translit_word = sa.rule_one(line);
			translit_word = sa.rule_two(translit_word);
			translit_word = sa.rule_three(translit_word);
			translit_word = sa.rule_four(translit_word);
			translit_word = sa.rule_five(translit_word);
			translit_word = sa.rule_six(translit_word);
			translit_word = sa.rule_seven(translit_word);
			translit_word = sa.rule_eight(translit_word);
			
			translitWords.add(translit_word);
			translitBufferedWriter.write(translit_word + "\n");
			
			line = translitBufferedReader.readLine();
			System.out.println(translitWords.size());
		}
		
		translitBufferedWriter.close();
		translitBufferedReader.close();
		
		// ------------------ Create SiEn Map ----------------------------------
		
		String map_name = name.concat("_SiENMap.txt");
		
		FileOutputStream mapFileOutputStream = new FileOutputStream(new File(map_name));
	    BufferedWriter mapBufferedWriter = new BufferedWriter(new OutputStreamWriter(mapFileOutputStream, "UTF8"));
	    
		System.out.println(uniqueWords.size());
		System.out.println(translitWords.size());
		for(int i=0; i<uniqueWords.size(); i++){
			mapBufferedWriter.write(uniqueWords.get(i) + "\t" + translitWords.get(i));
			mapBufferedWriter.write("\n");
		}
		
		mapBufferedWriter.close();
		
		// ---------------------------------------------------------------------
		
		// ----------------- Translit Sents ------------------------------------
		
		TranslitSents ts = new TranslitSents();
		Hashtable<String, String> map = ts.word_map(map_name);
		String sent_name = name.concat("_TranslitSents.txt");
		
		FileInputStream sentFileInputStream = new FileInputStream(new File(fileName));
		BufferedReader sentBufferedReader = new BufferedReader(new InputStreamReader(sentFileInputStream, "UTF8"));
		
		FileOutputStream sentFileOutputStream = new FileOutputStream(new File(sent_name));
	    BufferedWriter sentBufferedWriter = new BufferedWriter(new OutputStreamWriter(sentFileOutputStream));
	      
	
		String si_line = sentBufferedReader.readLine();
		//System.out.println(si_line);
		while(si_line != null){
			String[] words = si_line.trim().split(" ");
			System.out.println(words.length);
			String trans = "";
			String sent = "";
			for(int i=0; i< words.length; i++){
				trans = ts.translit(words[i]);
				System.out.println("TRANS = " + trans);
				trans = trans.replaceAll("-", "");
				if(sent.equals("")){
					sent = sent.concat(trans);
				}
				else
					sent = sent.concat(" ").concat(trans);
			}
			
			sentBufferedWriter.write(sent.concat("\n"));
			si_line = sentBufferedReader.readLine();
		}
		
		sentBufferedWriter.close();
		sentBufferedReader.close();

	}

}
